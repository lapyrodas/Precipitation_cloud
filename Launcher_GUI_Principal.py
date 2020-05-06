# -*- coding: utf-8 -*-
"""
Created on Mon Nov  4 15:24:55 2019

@author: Natalia
"""
import sys
import os

from PyQt5 import QtGui, QtCore, QtWidgets, uic
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QPushButton, QDialog, QMessageBox, QProgressBar, QWidget, QApplication
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtGui import QCursor

#Para copiar un archivo
from shutil import copyfile

#Carga el archivo py de procesamiento
from ProcesamientoImg import *

import time


#----------------------------------------
# Objetos globales
#----------------------------------------
PreprocesamientoIMG = {
    'p_texture' : None,
    'nombreFolder' : None,
    'rutaTemporal' : os.path.abspath(os.getcwd()) + os.sep + 'temporal',
    'rutaFolder': None,
    'rutaClasificadores': os.path.abspath(os.getcwd()) + os.sep + 'Clasificadores',
    'rutaEntradaImg': None,
    'rutaShape': None,
    'condicion': None,
    'existeShape': False
}

PreprocesamientoIMG = {'p_texture': 'C:\\Users\\Natalia\\Desktop\\ULTIMITO\\temporal\\20201081550167_20201081559486\\texture', 
'nombreFolder': '20201081550167_20201081559486', 
'rutaTemporal': 'C:\\Users\\Natalia\\Desktop\\ULTIMITO\\temporal', 
'rutaFolder': 'C:\\Users\\Natalia\\Desktop\\ULTIMITO\\temporal\\20201081550167_20201081559486', 
'rutaClasificadores': 'C:\\Users\\Natalia\\Desktop\\ULTIMITO\\Clasificadores', 
'rutaEntradaImg': 'C:/Users/Natalia/Downloads/OR_ABI-L2-MCMIPF-M6_G16_s20201081550167_e20201081559486_c20201081559574.nc', 
'rutaShape': None, 
'condicion': 'SVM', 
'existeShape': False}

#----------------------------------------
# CARGAR LA GUI INICIA LA CLASE
#----------------------------------------
qtCreatorFile = "InterfazNueva3.ui"  

Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)  

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, *args, **kwargs):
        QtWidgets.QMainWindow.__init__(self, *args, **kwargs)
        self.setupUi(self)

        self.setWindowTitle("Clasificación de nubes precipitables")
        
        #Abrir el escritorio para guardar la imagen 
        self.pushButton_buscarImagen.setToolTip(u'Obtener imagen .tif')
        self.pushButton_buscarImagen.clicked.connect(self.obtenerTIF)   

        #Carga la imagen y preprocesa
        self.pushButton_cargarImagen.setToolTip(u'Cargar imagen')
        self.pushButton_cargarImagen.clicked.connect(self.cargarTIF) 

        #Buscar el shape de la zona de estudio
        self.pushButton_buscarShape.clicked.connect(self.obtenerShape)   
 
        #Recorta la imagen de Colombia en formato RGB
        self.pushButton_cargarShape.clicked.connect(self.cargarShape)

        #Seleccionar todos checkbox
        self.pushButton_seleccionarTodas.clicked.connect(self.seleccionarTodas)

        #Limpiar todos checkbox
        self.pushButton_deseleccionarTodas.clicked.connect(self.desSeleccionarTodas)

        #Cambia el Checkbox
        self.checkBox_noPrecipitables.stateChanged.connect(self.cambiarMascaraNubes)
        self.checkBox_precipitables.stateChanged.connect(self.cambiarMascaraNubes)
        self.checkBox_sinNube.stateChanged.connect(self.cambiarMascaraNubes)

        #Procesar la imagen usando los clasificadores de la lista
        self.pushButton_procesar.clicked.connect(self.clasificar)

        #Guardar imagen clasificada
        self.pushButton_Guardar.clicked.connect(self.guardarTIF)

        #Inicia las variables del sistema
        self.init()
    
   
    def init(self):
        #Listar clasificadores, busca las carpetas en el directorio y las lista
        self.listarClasificadores()

        #QtGui.QMessageBox.about(self, u"Información", u"Esto es una ventana emergente")


    def obtenerTIF(self):
        filePath, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', '/desktop',"(*.nc)")
        PreprocesamientoIMG['rutaEntradaImg'] = filePath

        self.nombreFolder = (filePath[filePath.find("_s")+2:filePath.find("_e")]) + '_' + (filePath[filePath.find("_e")+2:filePath.find("_c")])
        
        #Mostrar el nombre de la imagen cargada
        self.pathimagen_4.setText(filePath)

       
    def cargarTIF(self):
        #Se inicializa el hilo: HiloCargarTIF
        self.hiloCargarTIF = QtCore.QThread(self)
        self.worker_hiloCargarTIF = HiloCargarTIF()
        self.worker_hiloCargarTIF.moveToThread(self.hiloCargarTIF)
        self.worker_hiloCargarTIF.finished.connect(self.handleFinished_cargarTIF)
        self.hiloCargarTIF.started.connect(self.worker_hiloCargarTIF.run)

        self.centralwidget.setEnabled(False)
        self.centralwidget.setCursor(QCursor(QtCore.Qt.WaitCursor))
        self.hiloCargarTIF.start()


    def handleFinished_cargarTIF(self):
        self.hiloCargarTIF.quit()
        self.hiloCargarTIF.wait()

        self.centralwidget.setEnabled(True)
        self.centralwidget.setCursor(QCursor(QtCore.Qt.ArrowCursor))


    def obtenerShape(self):
        rutaShape, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', '/desktop',"(*.shp)")
        
        #Mostrar el nombre de la imagen cargada
        self.pathshp.setText(rutaShape)

        PreprocesamientoIMG['rutaShape'] = rutaShape

        #Bandera en falso
        PreprocesamientoIMG['existeShape'] = False
        

    #Recorta la imagen de Colombia en formato RGB
    def cargarShape(self):
        #Bandera en True
        PreprocesamientoIMG['existeShape'] = True


    def clasificar(self):
        #Obtener el valor del comboBox_seleccionarClasificador
        PreprocesamientoIMG['condicion'] = str(self.comboBox_seleccionarClasificador.currentText())

        #Se inicializa el hilo: HiloCargarTIF
        self.hiloClasificar = QtCore.QThread(self)
        self.worker_hiloClasificar = HiloClasificar()
        self.worker_hiloClasificar.moveToThread(self.hiloClasificar)
        self.worker_hiloClasificar.finished.connect(self.handleFinished_clasificar)
        self.hiloClasificar.started.connect(self.worker_hiloClasificar.run)

        self.centralwidget.setEnabled(False)
        self.centralwidget.setCursor(QCursor(QtCore.Qt.WaitCursor))

        self.hiloClasificar.start()


    def handleFinished_clasificar(self):
        self.hiloClasificar.quit()
        self.hiloClasificar.wait()

        self.centralwidget.setEnabled(True)
        self.centralwidget.setCursor(QCursor(QtCore.Qt.ArrowCursor))

        print('FIN clasificar -Hilo2')

        nombreFolder = PreprocesamientoIMG['nombreFolder']
        rutaFolder = PreprocesamientoIMG['rutaFolder']
        rutaShape = PreprocesamientoIMG['rutaShape'] 
        rutaTemporal = PreprocesamientoIMG['rutaTemporal'] 
        existeShape = PreprocesamientoIMG['existeShape'] 

        try:
            stackColorTIF(rutaTemporal, nombreFolder)
        except:
            print("Error en stackColorTIF")
        print('FIN stackColorTIF -Hilo2')

        if(existeShape):
            recortarImg(rutaFolder, rutaShape, nombreFolder)
            print('FIN recortarImg -Hilo2')

        try:
            stackColorPNG(rutaFolder, existeShape)
        except:
            print("Error en stackColorPNG")
        print('FIN stackColorPNG -Hilo2')

        try:
            mascaraBandasPNG(rutaFolder, existeShape)
        except:
            print("Error en mascaraBandasPNG")
        print('FIN mascaraBandasPNG -Hilo2')
        mascaraNubes(rutaFolder, existeShape)
        try:
            mascaraNubes(rutaFolder, existeShape)
        except:
            print("Error en mascaraNubes")
        print('FIN mascaraNubes -Hilo2')
        
        try:
            pixmap = mostrarStackRBG(rutaFolder, existeShape)
            self.label_imgResultado.setPixmap(pixmap)
        except:
            print("Error en label_imgResultado")

            
    def seleccionarTodas(self):
        self.checkBox_noPrecipitables.setChecked(True)
        self.checkBox_precipitables.setChecked(True)
        self.checkBox_sinNube.setChecked(True)


    def desSeleccionarTodas(self):
        self.checkBox_noPrecipitables.setChecked(False)
        self.checkBox_precipitables.setChecked(False)
        self.checkBox_sinNube.setChecked(False)


    def listarClasificadores(self):
        dirs = os.listdir(PreprocesamientoIMG['rutaClasificadores'])
        self.comboBox_seleccionarClasificador.clear()
        self.comboBox_seleccionarClasificador.addItems(dirs)


    def cambiarMascaraNubes(self):
        rutaFolder = PreprocesamientoIMG['rutaFolder']
        existeShape = PreprocesamientoIMG['existeShape'] 

        if self.checkBox_noPrecipitables.isChecked():
            pixmap = mostrarPrecipitable(rutaFolder, existeShape)
            self.label_imgResultado.setPixmap(pixmap)
            print('1')
        elif self.checkBox_precipitables.isChecked():
            pixmap = mostrarNoPrecipitable(rutaFolder, existeShape)
            self.label_imgResultado.setPixmap(pixmap)
            print('2')
        elif self.checkBox_sinNube.isChecked():
            mostrarSinNube(rutaFolder, existeShape)
            print('0')
#------------------------------
 




    def guardarTIF(self):
        global filePath3
        filePath3, _= QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', '/desktop',"(*.tif)")
        
        #Mostrar el nombre de la imagen cargada
        self.pathguardar.setText(filePath3) 
        return (filePath3, _)




class HiloRecortarImagen(QtCore.QObject): #Worker
    finished = QtCore.pyqtSignal()

    def run(self):
        print('Test 1')
        time.sleep(1)
        print('Test 2')
        time.sleep(1)
        print('Test 3')
        time.sleep(1)
        self.finished.emit()


class HiloCargarTIF(QtCore.QObject):
    finished = QtCore.pyqtSignal()

    def __init__(self):
        QThread.__init__(self)
    
    def __del__(self):
        #self.wait()
        pass

    def run(self):
        rutaEntradaImg = PreprocesamientoIMG['rutaEntradaImg']
        
        print('Procesando ...')
        p_temporal, p_texture, nombreFolder = procesarImgEntrada(rutaEntradaImg)
        print('End ...')

        #PreprocesamientoIMG['p_temporal'] = p_temporal
        PreprocesamientoIMG['p_texture'] = p_texture
        PreprocesamientoIMG['nombreFolder'] = nombreFolder
        PreprocesamientoIMG['rutaFolder'] = p_temporal
        
        self.finished.emit()


class HiloClasificar(QtCore.QObject):
    finished = QtCore.pyqtSignal()

    def __init__(self):
        QThread.__init__(self)
    
    def __del__(self):
        #self.wait()
        pass

    def run(self):
        print('objetos ahora ---------------------------------')
        print(PreprocesamientoIMG)
        print('--------------------------------------------------')

        p_texture = PreprocesamientoIMG['p_texture']
        rutaFolder = PreprocesamientoIMG['rutaFolder']
        rutaClasificadores = PreprocesamientoIMG['rutaClasificadores']
        condicion = PreprocesamientoIMG['condicion']
        
        entradas, dim = sort_texture(p_texture)

        prediccion, _ = clasificar(entradas, rutaClasificadores, condicion)

        prediccion, tipo = sort_prediccion(prediccion, dim, condicion)

        outpath = rutaFolder + os.sep + 'mask_CLASIFICACION.tif'

        #Cuando termina de clasificar se guarda la mascara resultnte
        save_img(outpath, prediccion)

        self.finished.emit()
        


         
if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    #sys.exit(app.exec_())
    app.exec_()


