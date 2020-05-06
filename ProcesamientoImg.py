from netCDF4 import Dataset  
import talos
import keras
import os, shutil
import glob
import numpy as np
import gdal_merge as gm
from joblib import load
import rpy2.robjects as ro
import rpy2.robjects.numpy2ri 
import gdal
import subprocess
import cv2
import sys

from PyQt5.QtGui import QIcon, QPixmap

def preprocesamiento(p_nc, textura):
    #Crear carpeta temporal donde se almacenan los tiff,las texturas y las mascaras.
    temporal = os.path.abspath(os.getcwd()) + os.sep + 'temporal'
    create_folder(temporal)
    
    #Nombre de la carpeta dentro de temporal
    folder = (p_nc[p_nc.find("_s")+2:p_nc.find("_e")]) + '_' + (p_nc[p_nc.find("_e")+2:p_nc.find("_c")])
    
    path = temporal + os.sep + folder
    create_folder(path)

    out_texture = path + os.sep + 'texture' + os.sep
    out_texture2 = path + os.sep + 'texture'
    create_folder(out_texture)
    
    #Parametros imagen - Coordenadas de Colombia
    limit = (2024,2948,2340,3156) ## min_lat_idx:max_lat_idx,min_lon_idx:max_lon_idx
    bandas = {1:'CMI_C01', 2:'CMI_C02', 3:'CMI_C03', 8:'CMI_C08', 9:'CMI_C09', 10:'CMI_C10', 13:'CMI_C13'}
    names = {1:'blue', 2:'red', 3:'nir', 8:'vw_h', 9:'vw_m', 10:'vw_l', 13:'tir_13'}
    
    file = Dataset(p_nc)
    
    for key in bandas:
        #Corta la imagen de Colombia		
        data = file.variables[bandas[key]][limit[0]:limit[1],limit[2]:limit[3]][::1,::1]
        
        outpath = path + os.sep + names[key] + '.tif'	
        save_img(outpath, data)
        
        nombre = names[key]
        textura(outpath, out_texture, nombre)
    
    return (path, out_texture2, folder)


def save_img(outpath, data):
    #Obtengo el driver dependiendo de el tipo de imagen
    driver = gdal.GetDriverByName('GTiff')
    (upper_left_x, x_size, x_rotation, upper_left_y, y_rotation, y_size)=-81.77,0.018267326732673256,0,12.59,0,-0.018246753246753247
    projection = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
    row = data.shape[0]
    path = data.shape[1]
    export = driver.Create(outpath,path,row,1,gdal.GDT_Float64)
    banda = export.GetRasterBand(1)
    banda.WriteArray(data)
    export.SetGeoTransform((upper_left_x, x_size, x_rotation, upper_left_y, y_rotation, y_size))
    export.SetProjection(projection)
    banda.FlushCache()
    export.FlushCache()
	

def create_folder(path):
	if not os.path.exists(path):
		os.mkdir(path)


def procesarImgEntrada(pathEntrada):
    rpy2.robjects.numpy2ri.activate()

    codigo_r = """ 
    .libPaths(c("C:/Users/Natalia/Documents/R/win-library/3.6", "C:/Program Files/R/R-3.6.3/library"))
    library(raster)       # raster data
    library(rasterVis)    # raster visualisation
    library(sp)           # Spatial data
    library(rgdal)        # sptaial data 
    library(RStoolbox)    # Image analysis
    library(ggplot2)      # advap_nce plotting
    library(glcm)         # texture analysis
    textura <- function(path,output,nombre) {
    img = raster(path)
    glcm.img <- glcm(img,
                    window = c(3, 3),
                    shift=list(c(0,1), c(1,1), c(1,0), c(1,-1)), 
                    statistics = c("mean",
                                    "variance",
                                    "homogeneity"))
    b=(glcm.img-minValue(glcm.img))/(maxValue(glcm.img)-minValue(glcm.img))
    writeRaster(b, output,  paste0(nombre,'_', names(glcm.img)), bylayer=T, overwrite=TRUE, format="GTiff")
    }
    """

    ro.r(codigo_r)
    textura = ro.globalenv['textura']

    #Temporal es la ruta a los tiff, texture a las texturas
    p_temporal, p_texture, nombreFolder = preprocesamiento(pathEntrada, textura)

    return (p_temporal, p_texture, nombreFolder)


#Organizza la imagen para obtener el vector de caracteristicas para el clasificador
def sort_texture(p_texture):
    l_texture = glob.glob(p_texture + os.sep + '*.tif')
    entradas = np.empty((21,753984))

    for img in l_texture:    
        texture = gdal.Open(img).ReadAsArray()
        texture[[texture<0]]=np.nan
        n=texture.reshape((-1))
        entradas[l_texture.index(img)]=n
    
    entradas = entradas.T
    entradas[[np.isnan(entradas)]] = 0
    shape = texture.shape
    
    return (entradas, shape)


#Usa los clasificadores dependiendo de la GUI
def clasificar(entradas, ruta_clasificadores, condicion):
    print('DEBUG .... ruta_clasificadores', ruta_clasificadores)
    print('DEBUG .... condicion', condicion)

    if condicion =='RANDOM FOREST':
        clasificador = load(ruta_clasificadores + os.sep + 'RANDOM FOREST' + os.sep + 'Random Forest.pkl')
        prediccion = clasificador.predict(entradas).astype(float)
    elif condicion =='SVM':
        clasificador = load(ruta_clasificadores + os.sep + 'SVM' + os.sep + 'SVM.pkl')
        prediccion = clasificador.predict(entradas).astype(float)
    elif condicion =='MLP':
        keras.backend.clear_session()
        clasificador = talos.Restore(ruta_clasificadores + os.sep + 'MLP' + os.sep + 'cloud_model.zip')
        entradas = talos.utils.rescale_meanzero(entradas)
        prediccion = clasificador.model.predict(entradas).astype(float)
    else:
        print('ERROR: Clasificador no valido')
    

    print('DEBUG .... condicion', condicion)
    return(prediccion, clasificador)


#Organiza la imagen resultante
def sort_prediccion(prediccion, dim, condicion):
    if condicion=='RANDOM FOREST':
       tipo = 'rf'
    elif condicion=='SVM':
        tipo = 'svm'
    elif condicion=='MLP':
        tipo = 'mlp'
        prediccion = np.argmax(prediccion,axis=1)
        prediccion += 1
    
    prediccion = prediccion.reshape(dim).astype(float)
    prediccion[[prediccion==3]] = np.nan

    return(prediccion, tipo)


def recortarImg(rutaFolder, rutaShape, nombreFolder):
    salida = os.path.abspath(os.getcwd()) + os.sep + 'temporal' + os.sep + nombreFolder +  os.sep + 'recorte'
    aux = os.path.abspath(os.getcwd())

    print('rutaFolder: ', rutaFolder)
    print('rutaShape: ', rutaShape)
    print('salida: ', salida)

    if os.path.exists(salida): 
        shutil.rmtree(salida)
    
    create_folder(salida)

    rasters = glob.glob(rutaFolder + os.sep + '*.tif')

    for raster in rasters: 
        print ("archvio a recortar: " + raster)
        corte = salida + os.sep + os.path.basename(raster)
        a = ( 'gdalwarp -dstnodata 0 -q -cutline %s -crop_to_cutline -of GTiff %s %s' %(rutaShape, raster, corte) )
        print()
        print('Comando:')
        print(a)
        print()
        subprocess.call(a)


#Se hace el append de las bandas y se guarda la imagen generada
def stackColorPNG(rutaFolder, existeShape):
    if(existeShape):
        img_blue = rutaFolder + os.sep  + 'recorte' + os.sep + 'blue.tif'
        img_red = rutaFolder + os.sep  + 'recorte' + os.sep +  'red.tif'
        img_nir = rutaFolder + os.sep  + 'recorte' + os.sep +  'nir.tif'
        ruta_salida = rutaFolder + os.sep  + 'recorte' + os.sep +  'stackColor.png'
    else:
        img_blue = rutaFolder + os.sep  + 'blue.tif'
        img_red = rutaFolder + os.sep  + 'red.tif'
        img_nir = rutaFolder + os.sep  + 'nir.tif'
        ruta_salida = rutaFolder + os.sep +  'stackColor.png'

    blue = gdal.Open(img_blue)
    band = blue.GetRasterBand(1)
    arr1 = band.ReadAsArray()

    red = gdal.Open(img_red)
    band = red.GetRasterBand(1)
    arr2 = band.ReadAsArray()

    nir = gdal.Open(img_nir)
    band = nir.GetRasterBand(1)
    arr3 = band.ReadAsArray()

    h1, w1 = arr3.shape
    imgOutput = np.zeros((h1, w1, 3), np.uint8) 

    arr1 *= 255.0/arr1.max() 
    arr2 *= 255.0/arr2.max() 
    arr3 *= 255.0/arr3.max() 

    imgOutput[:, :, 0] = arr2 #R
    imgOutput[:, :, 1] = arr3 #G
    imgOutput[:, :, 2] = arr1 #B

    cv2.imwrite(ruta_salida, imgOutput)  


def stackColorTIF(rutaTemporal, nombreFolder):
    l_img = glob.glob(rutaTemporal + os.sep + nombreFolder + os.sep +'*.tif')
    
    blue = [s for s in l_img if "blue.tif" in s][0]
    red = [s for s in l_img if "red.tif" in s][0]
    nir = [s for s in l_img if "nir.tif" in s][0]

    sal_final = rutaTemporal + os.sep + nombreFolder + os.sep + 'stack_color.tif'   
    gm.main(['', '-separate', '-o', sal_final, red, nir, blue])


def mascaraBandasPNG(rutaFolder, existeShape):
    if(existeShape):
        img_mask = rutaFolder + os.sep  + 'recorte' + os.sep + 'mask_CLASIFICACION.tif'
        ruta_salida_0 = rutaFolder + os.sep  + 'recorte' + os.sep +  '00.png'
        ruta_salida_1 = rutaFolder + os.sep  + 'recorte' + os.sep +  '01.png'
        ruta_salida_2 = rutaFolder + os.sep  + 'recorte' + os.sep +  '02.png'
    else:
        img_mask = rutaFolder + os.sep  + 'mask_CLASIFICACION.tif'
        ruta_salida_0 = rutaFolder + os.sep + '00.png'
        ruta_salida_1 = rutaFolder + os.sep + '01.png'
        ruta_salida_2 = rutaFolder + os.sep + '02.png'

    img = gdal.Open(img_mask)
    band = img.GetRasterBand(1)
    arr = band.ReadAsArray()

    index_nan = np.isnan(arr)
    arr[index_nan] = 0

    mask_h, mask_w = arr.shape
    mask = np.zeros((mask_h, mask_w), np.uint8) 
    
    arr_0 = np.copy(mask)
    arr_1 = np.copy(mask)
    arr_2 = np.copy(mask)

    #Mascara con valores [0.1.2]
    mask = arr

    index_0 = np.where(mask == 0)
    index_1 = np.where(mask == 1)
    index_2 = np.where(mask == 2)

    arr_0[index_0] = 255
    arr_1[index_1] = 255
    arr_2[index_2] = 255

    cv2.imwrite(ruta_salida_0, arr_0)  
    cv2.imwrite(ruta_salida_1, arr_1)  
    cv2.imwrite(ruta_salida_2, arr_2)  


def mostrarStackRBG(rutaFolder, existeShape):
    if(existeShape):
        img_rgb = rutaFolder + os.sep  + 'recorte' + os.sep + 'stackColor.png'
    else:
        img_rgb = rutaFolder + os.sep  + 'stackColor.png'
        
    return QPixmap(img_rgb)


def mostrarNoPrecipitable(rutaFolder, existeShape):
    if(existeShape):
        img_rgb = rutaFolder + os.sep  + 'recorte' + os.sep + 'mascaraNubes02.png'
    else:
        img_rgb = rutaFolder + os.sep  + 'mascaraNubes02.png'
        
    return QPixmap(img_rgb)


def mostrarPrecipitable(rutaFolder, existeShape):
    if(existeShape):
        img_rgb = rutaFolder + os.sep  + 'recorte' + os.sep + 'mascaraNubes01.png'
    else:
        img_rgb = rutaFolder + os.sep  + 'mascaraNubes01.png'
        
    return QPixmap(img_rgb)


def mostrarSinNube(rutaFolder, existeShape):
    print('NO MUESTRO NADA :(')

    
def mascaraNubes(rutaFolder, existeShape):
    if(existeShape):
        print('ESTOYYYY EN EL IFFF -- mascaraNubes')
        img_mask_1 = rutaFolder + os.sep  + 'recorte' + os.sep + '01.png'
        img_mask_2 = rutaFolder + os.sep  + 'recorte' + os.sep + '02.png'
        img_base = rutaFolder + os.sep  + 'recorte' + os.sep + 'stackColor.png'
        ruta_salida_1 = rutaFolder + os.sep  + 'recorte' + os.sep + 'mascaraNubes01.png'
        ruta_salida_2 = rutaFolder + os.sep  + 'recorte' + os.sep + 'mascaraNubes02.png'
    else:
        img_mask_1 = rutaFolder + os.sep + '01.png'
        img_mask_2 = rutaFolder + os.sep + '02.png'
        img_base = rutaFolder + os.sep + 'stackColor.png'
        ruta_salida_1 = rutaFolder + os.sep + 'mascaraNubes01.png'
        ruta_salida_2 = rutaFolder + os.sep + 'mascaraNubes02.png'

    img_BASE = cv2.imread(img_base, cv2.IMREAD_COLOR)
    mask1 = cv2.imread(img_mask_1, cv2.IMREAD_COLOR)
    mask2 = cv2.imread(img_mask_2, cv2.IMREAD_COLOR)

    h1, w1, canales = mask2.shape
    mask_color = np.zeros((h1, w1, 3), np.uint8) 
   
    index1 = np.where(mask1[:, :, 0] == 255)
    
    zeros_0, zeros_1, zeros_2 = np.zeros((h1, w1), np.uint8), np.zeros((h1, w1), np.uint8), np.zeros((h1, w1), np.uint8)

    zeros_0[index1] = 247  #B
    zeros_1[index1] = 254  #G
    zeros_2[index1] = 46   #R

    mask_color[:, :, 0] = zeros_0
    mask_color[:, :, 1] = zeros_1
    mask_color[:, :, 2] = zeros_2

    res1 = cv2.add(mask_color,img_BASE)

    zeros_0.fill(0); zeros_1.fill(0); zeros_2.fill(0)
    mask_color.fill(0); mask_color.fill(0); mask_color.fill(0)

    index2 = np.where(mask2[:, :, 0] == 255)

    zeros_0[index2] = 255  #B
    zeros_1[index2] = 0  #G
    zeros_2[index2] = 0   #R

    mask_color[:, :, 0] = zeros_0
    mask_color[:, :, 1] = zeros_1
    mask_color[:, :, 2] = zeros_2

    res2 = cv2.add(mask_color,img_BASE)

    zeros_0.fill(0); zeros_1.fill(0); zeros_2.fill(0)
    mask_color.fill(0); mask_color.fill(0); mask_color.fill(0)

    cv2.imwrite(ruta_salida_1, res1)  
    cv2.imwrite(ruta_salida_2, res2)  







if __name__ == "__main__":

    #Path de entrada
    p_nc = r"C:\Users\Natalia\Downloads\OR_ABI-L2-MCMIPF-M6_G16_s20201081550167_e20201081559486_c20201081559574.nc"
    
    #Crear los shapes y recortar
    p_temporal, p_texture, nombreFolder = procesarImgEntrada(p_nc)
    
    #Cargar la imagen y usar los clasificadores
    ruta_clasificadores = 'Clasificadores'
    condicion ='Random Forest' # -> viene desde la interfaz el la

    entradas, dim = sort_texture(p_texture)
    prediccion, clasificador = clasificar(entradas, ruta_clasificadores, condicion)
    prediccion, tipo =  sort_prediccion(prediccion, dim, condicion)
    outpath = p_temporal+os.sep+'mask_ULTIMITO_'+tipo+'.tif' 
    #outpath = p_temporal+os.sep+'mask_ULTIMITO_'+tipo+'.jpg' 
    save_img(outpath,prediccion)





