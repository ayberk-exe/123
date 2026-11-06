"""Native Qt editor and VTK scene, separate from Streamlit."""

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from marineprop.geometry import (
    PropellerDesign, RadialStation, export_stl, generate_propeller, load_design,
    reference_designs, save_design,
)


class GeometryWorker(QObject):
    done = Signal(object, object)
    finished = Signal()

    def __init__(self, design):
        super().__init__()
        self.design=design

    def run(self):
        try:
            self.done.emit(generate_propeller(self.design), None)
        except Exception as exc:
            self.done.emit(None, str(exc))
        finally:
            self.finished.emit()


class PropellerWindow(QMainWindow):
    geometry_ready = Signal(object)
    generation_failed = Signal(str)

    def __init__(self, offscreen=False):
        super().__init__()
        self.setWindowTitle('MarineProp Studio — v0.2 Parametric Designer')
        self.resize(1400,900)
        self.geometry=None
        self._busy=False
        self._pending=None
        self._loading=True
        self._revision=0
        self._active_revision=-1
        self._reset_camera=True
        self._thread=None
        self.timer=QTimer(self); self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.regenerate)
        splitter=QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)
        panel=QWidget(); controls=QVBoxLayout(panel)
        title=QLabel('Pervane tasarımı / Propeller geometry'); title.setStyleSheet('font-size:18px;font-weight:bold')
        controls.addWidget(title)
        note=QLabel('SI motoru · giriş mm\nD değişimi göbeği orantılı ölçekler.\nGeometri KT/KQ veya itme tahmini değildir.')
        note.setWordWrap(True); controls.addWidget(note)
        form=QFormLayout(); controls.addLayout(form)
        self.diameter=self._number(form,'Çap D (mm)',1,10000,80)
        self.blades=QSpinBox(); self.blades.setRange(2,12); self.blades.setValue(3)
        form.addRow('Kanat sayısı / Blades',self.blades)
        self.hub_diameter=self._number(form,'Göbek çapı (mm)',.1,9999,18)
        self.hub_length=self._number(form,'Göbek boyu (mm)',.1,10000,24)
        self.pitch=self._number(form,'P/D',.05,5,.8,9)
        self.rake=self._number(form,'Rake: kök → uç (mm)',-9999,9999,0)
        self.skew=self._number(form,'Skew: kök → uç (°)',-89,89,15)
        self.hand=QComboBox(); self.hand.addItems(['Sağ / Right','Sol / Left']); form.addRow('Helis yönü',self.hand)
        self.presets=QComboBox(); self.presets.addItems(['80 mm · 3 kanat · P/D 0.8','120 mm · 4 kanat · P/D 1.0','60 mm · 2 kanat · P/D 0.6'])
        controls.addWidget(self.presets)
        preset=QPushButton('Referans tasarımı uygula'); preset.clicked.connect(self.apply_preset); controls.addWidget(preset)
        hint=QLabel('Radyal dağılımlar: c/D, t/c ve yerel P/D çarpanı.\nProfil: naca00 veya ellipse; karışık profiller doğrusal loft edilir.\nKök göbeğin içinde; uç r/R=1, pozitif kord ve kalınlıkla kapatılır.')
        hint.setWordWrap(True); controls.addWidget(hint)
        self.table=QTableWidget(0,5)
        self.table.setHorizontalHeaderLabels(['r/R','c/D','t/c','P/D ×','Profil'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(230); controls.addWidget(self.table)
        rowbuttons=QHBoxLayout(); controls.addLayout(rowbuttons)
        add=QPushButton('Kesit ekle'); remove=QPushButton('Kesit sil')
        add.clicked.connect(self.add_station); remove.clicked.connect(self.remove_station)
        rowbuttons.addWidget(add); rowbuttons.addWidget(remove)
        self.regenerate_button=QPushButton('Geometriyi yeniden üret'); self.regenerate_button.clicked.connect(self.regenerate)
        controls.addWidget(self.regenerate_button)
        self.auto=QCheckBox('Değişiklikte otomatik üret'); self.auto.setChecked(True); controls.addWidget(self.auto)
        self.edges=QCheckBox('Yüzey kenarları'); self.edges.toggled.connect(self.redraw); controls.addWidget(self.edges)
        self.axes=QCheckBox('Koordinat eksenleri'); self.axes.setChecked(True); self.axes.toggled.connect(self.toggle_axes); controls.addWidget(self.axes)
        views=QHBoxLayout(); controls.addLayout(views)
        for label,method in [('Ön (+Z)',self.front_view),('Yan (+X)',self.side_view),('İzometrik',self.iso_view),('Kamera sıfırla',self.reset_camera)]:
            button=QPushButton(label); button.clicked.connect(method); views.addWidget(button)
        files=QHBoxLayout(); controls.addLayout(files)
        save=QPushButton('Tasarımı kaydet'); save.clicked.connect(self.save_dialog); files.addWidget(save)
        load=QPushButton('Tasarım aç'); load.clicked.connect(self.load_dialog); files.addWidget(load)
        self.units=QComboBox(); self.units.addItems(['mm — baskı/CAD','m — CFD']); controls.addWidget(self.units)
        self.export_button=QPushButton('Doğrulanmış STL dışa aktar'); self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_dialog); controls.addWidget(self.export_button)
        controls.addWidget(QLabel('STEP: kullanılamıyor — CAD B-rep çekirdeği eklenmedi.'))
        self.status=QLabel('Geometri hazırlanıyor…'); self.status.setWordWrap(True); controls.addWidget(self.status)
        controls.addStretch()
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(panel); scroll.setMinimumWidth(460)
        splitter.addWidget(scroll)
        view=QWidget(); layout=QVBoxLayout(view)
        helptext=QLabel('Sol sürükle: döndür · tekerlek: zoom · orta/Shift+sol sürükle: pan · Z şaft ekseni · görünüm mm')
        helptext.setWordWrap(True); layout.addWidget(helptext)
        self.plotter=QtInteractor(view,off_screen=offscreen)
        self.plotter.set_background('#132334')
        if self.plotter.iren is not None:
            self.plotter.enable_trackball_style()
        self.plotter.add_axes()
        layout.addWidget(self.plotter.interactor)
        splitter.addWidget(view); splitter.setStretchFactor(1,1); splitter.setSizes([490,910])
        self._previous_diameter=80.
        self.diameter.valueChanged.connect(self.diameter_changed)
        for control in (self.hub_diameter,self.hub_length,self.pitch,self.rake,self.skew):
            control.valueChanged.connect(self.changed)
        self.blades.valueChanged.connect(self.changed)
        self.hand.currentIndexChanged.connect(self.changed)
        self.table.cellChanged.connect(self.changed)
        self.set_design(PropellerDesign())
        QTimer.singleShot(0,self.regenerate)

    def set_status(self,message):
        self.status.setText(message)
        self.statusBar().showMessage(message.splitlines()[0])

    def _number(self,form,label,minimum,maximum,value,decimals=9):
        spin=QDoubleSpinBox(); spin.setDecimals(decimals); spin.setRange(minimum,maximum)
        spin.setValue(value); spin.setKeyboardTracking(False)
        form.addRow(label,spin); return spin

    def set_design(self,design):
        for value,widget in ((design.diameter_m*1000,self.diameter),
            (design.hub_diameter_m*1000,self.hub_diameter),(design.hub_length_m*1000,self.hub_length),
            (design.pitch_ratio,self.pitch),(design.rake_m*1000,self.rake),(design.skew_deg,self.skew)):
            if not widget.minimum() <= value <= widget.maximum():
                raise ValueError('Tasarım masaüstü giriş aralığı dışında; değerler kırpılmadı')
        self._loading=True
        self.diameter.setValue(design.diameter_m*1000)
        self._previous_diameter=self.diameter.value()
        self.hub_diameter.setValue(design.hub_diameter_m*1000)
        self.hub_length.setValue(design.hub_length_m*1000)
        self.blades.setValue(design.blade_count); self.pitch.setValue(design.pitch_ratio)
        self.rake.setValue(design.rake_m*1000); self.skew.setValue(design.skew_deg)
        self.hand.setCurrentIndex(0 if design.handedness=='right' else 1)
        self.table.setRowCount(len(design.stations))
        for i,station in enumerate(design.stations):
            for j,value in enumerate((station.radius_fraction,station.chord_ratio,station.thickness_ratio,station.pitch_factor,station.profile)):
                self.table.setItem(i,j,QTableWidgetItem(str(value)))
        self._section_points=design.section_points
        self._radial_subdivisions=design.radial_subdivisions
        self._loading=False
        self.changed()

    def read_design(self):
        stations=[]
        for row in range(self.table.rowCount()):
            cells=[self.table.item(row,i).text().strip() if self.table.item(row,i) else '' for i in range(5)]
            try:
                stations.append(RadialStation(*[float(c) for c in cells[:4]],profile=cells[4]))
            except ValueError as exc:
                raise ValueError(f'Kesit {row+1}: geçerli sayılar ve profil adı girin') from exc
        return PropellerDesign(diameter_m=self.diameter.value()/1000,blade_count=self.blades.value(),
            hub_diameter_m=self.hub_diameter.value()/1000,hub_length_m=self.hub_length.value()/1000,
            pitch_ratio=self.pitch.value(),rake_m=self.rake.value()/1000,skew_deg=self.skew.value(),
            handedness='right' if self.hand.currentIndex()==0 else 'left',stations=tuple(stations),
            section_points=self._section_points,radial_subdivisions=self._radial_subdivisions)

    def diameter_changed(self,value):
        if self._loading: return
        ratio=value/self._previous_diameter
        self._loading=True
        self.hub_diameter.setValue(self.hub_diameter.value()*ratio)
        self.hub_length.setValue(self.hub_length.value()*ratio)
        self.rake.setValue(self.rake.value()*ratio)
        self._previous_diameter=value; self._loading=False
        self.changed()

    def changed(self,*args):
        if self._loading: return
        self._revision+=1
        self.export_button.setEnabled(False)
        self.set_status('Girdiler değişti. Görünüm son geçerli modele aittir; STL güncel değil.')
        if self.auto.isChecked(): self.timer.start(400)

    def add_station(self):
        # Insert before selected row; user specifies a strictly increasing radius.
        index=max(0,self.table.currentRow()); self.table.insertRow(index)
        self.changed()

    def remove_station(self):
        if self.table.currentRow()>=0: self.table.removeRow(self.table.currentRow()); self.changed()

    def apply_preset(self):
        self.set_design(reference_designs()[self.presets.currentIndex()]); self.regenerate()

    def regenerate(self):
        self.timer.stop()
        try: design=self.read_design()
        except (ValueError,TypeError) as exc:
            self.set_status(f'Geometri hatası: {exc}\nSon geçerli görünüm korunuyor; STL devre dışı.')
            self.export_button.setEnabled(False); self.generation_failed.emit(str(exc)); return
        if self._busy:
            self._pending=design; return
        self._busy=True; self._pending=None; self._active_revision=self._revision
        self.export_button.setEnabled(False); self.set_status('Kesit loftu ve göbek boolean birleşimi hesaplanıyor…')
        self._thread=QThread(self)
        self._worker=GeometryWorker(design); self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self.completed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self.thread_finished)
        self._thread.start()

    def completed(self,geometry,error):
        if self._active_revision != self._revision:
            return # never publish or export a result computed for obsolete inputs
        if error:
            self.set_status(f'Geometri hatası: {error}\nSon geçerli görünüm korunuyor; STL devre dışı.')
            self.generation_failed.emit(error); return
        self.geometry=geometry
        report=geometry.validate()
        self.redraw()
        self.export_button.setEnabled(True)
        self.set_status(f"D={report['diameter_m']*1000:.3f} mm · {report['blade_count']} kanat\n"
            f"{report['triangles']} üçgen · tek kapalı solid · dışa dönük normaller\n"
            f"Hacim={report['volume_m3']*1e9:.2f} mm³\nGeometrik doğrulama; hidrodinamik/üretim onayı değildir.")
        self.geometry_ready.emit(geometry)

    def thread_finished(self):
        self._thread.deleteLater(); self._thread=None; self._worker=None; self._busy=False
        if self._pending is not None:
            self._pending=None; self.regenerate()

    def redraw(self,*args):
        if self.geometry is None: return
        mesh=self.geometry.mesh
        faces=np.column_stack((np.full(len(mesh.faces),3),mesh.faces)).ravel()
        surface=pv.PolyData(mesh.vertices*1000,faces)
        self.plotter.add_mesh(surface,name='propeller',color='#d9a75f',show_edges=self.edges.isChecked(),
            smooth_shading=True,split_sharp_edges=True,feature_angle=40,reset_camera=False)
        if self._reset_camera:
            self.plotter.view_isometric(); self.plotter.reset_camera(); self._reset_camera=False
        self.plotter.render()

    def toggle_axes(self,on):
        self.plotter.show_axes() if on else self.plotter.hide_axes()
        self.plotter.render()

    def front_view(self): self.plotter.view_xy(); self.plotter.reset_camera()
    def side_view(self): self.plotter.view_yz(); self.plotter.reset_camera()
    def iso_view(self): self.plotter.view_isometric(); self.plotter.reset_camera()
    def reset_camera(self): self.plotter.reset_camera()

    def save_to(self,path): save_design(self.read_design(),path)
    def load_from(self,path): self.set_design(load_design(path)); self._reset_camera=True; self.regenerate()

    def export_to(self,path,unit=None):
        if self.geometry is None or not self.export_button.isEnabled() or self.geometry.design != self.read_design():
            raise ValueError('Güncel, doğrulanmış geometri olmadan STL dışa aktarılamaz')
        export_stl(self.geometry,path,unit or ('mm' if self.units.currentIndex()==0 else 'm'))

    def _file_action(self,action):
        try: action()
        except (ValueError,TypeError,OSError,KeyError) as exc: self.set_status(f'Dosya/geometri hatası: {exc}')

    def save_dialog(self):
        path,_=QFileDialog.getSaveFileName(self,'Tasarımı kaydet','','MarineProp JSON (*.json)')
        if path: self._file_action(lambda:self.save_to(path))

    def load_dialog(self):
        path,_=QFileDialog.getOpenFileName(self,'Tasarım aç','','MarineProp JSON (*.json)')
        if path: self._file_action(lambda:self.load_from(path))

    def export_dialog(self):
        path,_=QFileDialog.getSaveFileName(self,'STL dışa aktar','','STL mesh (*.stl)')
        if path: self._file_action(lambda:self.export_to(path))

    def closeEvent(self,event):
        self.timer.stop(); self._pending=None
        if self._thread is not None:
            self._thread.quit(); self._thread.wait()
        self.plotter.close(); event.accept()
