r"""Native Qt/VTK acceptance workflow. Requires a display (or virtual X server).

Windows: .venv-cad\Scripts\python.exe scripts/desktop_smoke.py
Linux: DISPLAY=:97 .venv-cad/bin/python scripts/desktop_smoke.py
Does not require a browser or Streamlit. Artifacts default to /tmp on Linux via
--output, or a temporary directory if omitted. Not a Windows certification.
"""
import argparse
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pyvista as pv
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from marineprop.desktop.window import PropellerWindow
from marineprop.geometry import mesh_report


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    out=args.output or Path(tempfile.mkdtemp(prefix='marineprop-desktop-'))
    out.mkdir(parents=True,exist_ok=True)
    app=QApplication([]); window=PropellerWindow(); window.show()
    failures=[]; window.generation_failed.connect(failures.append)

    def wait_ready():
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            app.processEvents(); QTest.qWait(20)
            if failures: raise AssertionError(failures)
            if window.export_button.isEnabled() and not window._busy and not window.timer.isActive(): return
        raise AssertionError('Geometry worker timed out: '+window.status.text())

    try:
        wait_ready()
        first=window.geometry
        assert first.design.blade_count==3 and first.design.diameter_m==.08 and first.design.pitch_ratio==.8
        assert window.plotter.iren is not None
        # Actual Qt mouse interaction must change VTK camera orientation.
        before=np.array(window.plotter.camera.position)
        widget=window.plotter.interactor
        center=QPoint(widget.width()//2,widget.height()//2)
        QTest.mousePress(widget,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,center)
        for i in range(1,9):
            QTest.mouseMove(widget,center+QPoint(i*9,i*5),30)
        QTest.mouseRelease(widget,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,center+QPoint(72,40))
        app.processEvents()
        assert not np.allclose(before,window.plotter.camera.position),'Mouse rotation did not change camera'
        # Pan, zoom and standard camera actions operate on the live VTK renderer.
        pos_before=np.array(window.plotter.camera.position)
        QTest.mousePress(widget,Qt.MouseButton.MiddleButton,Qt.KeyboardModifier.NoModifier,center)
        for i in range(1,5): QTest.mouseMove(widget,center+QPoint(i*8,0),30)
        QTest.mouseRelease(widget,Qt.MouseButton.MiddleButton,Qt.KeyboardModifier.NoModifier,center+QPoint(32,0))
        app.processEvents()
        assert not np.allclose(pos_before,window.plotter.camera.position),'Mouse pan did not change camera'
        angle=window.plotter.camera.view_angle
        window.plotter.camera.zoom(1.3); window.plotter.render()
        assert window.plotter.camera.view_angle < angle
        for method in (window.front_view,window.side_view,window.iso_view,window.reset_camera): method(); app.processEvents()
        window.edges.setChecked(True); window.axes.setChecked(False); window.axes.setChecked(True)
        app.processEvents()
        window.plotter.screenshot(str(out/'viewport_3_blades.png'))
        window.edges.setChecked(False); app.processEvents()
        window.grab().save(str(out/'desktop_3_blades.png'))
        window.save_to(out/'design.json')
        window.export_to(out/'propeller_80mm_3blades.stl')
        read=pv.read(out/'propeller_80mm_3blades.stl').clean()
        assert read.n_open_edges==0
        assert np.isclose(2*np.linalg.norm(read.points[:,:2],axis=1).max(),80,rtol=3e-6)
        assert np.unique(read.connectivity()['RegionId']).size==1
        window.blades.setValue(4)
        assert not window.export_button.isEnabled()
        try: window.export_to(out/'stale.stl')
        except ValueError: pass
        else: raise AssertionError('Stale mesh was exported')
        wait_ready(); assert len(window.geometry.blades)==4
        four=window.geometry.blades[0].vertices.copy()
        window.pitch.setValue(1.1); wait_ready()
        assert not np.allclose(four,window.geometry.blades[0].vertices)
        assert window.geometry.validate()['watertight']
        window.export_to(out/'propeller_80mm_4blades.stl')
        window.plotter.screenshot(str(out/'viewport_4_blades.png'))
        window.load_from(out/'design.json'); wait_ready()
        assert window.geometry.design==first.design
        # A malformed table must give a visible error and disable stale STL export.
        window.table.item(0,2).setText('0')
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and not failures:
            app.processEvents(); QTest.qWait(20)
        assert failures and not window.export_button.isEnabled()
        assert 'hat' in window.statusBar().currentMessage().lower()
        image=pv.read_texture(out/'viewport_3_blades.png').to_image().active_scalars
        assert np.unique(image,axis=0).shape[0]>50,'Renderer produced a blank image'
        print('PASS: native Qt launch; D80/P-D0.8; 3→4 blades; pitch change; mouse rotate/pan; zoom/views/edges/axes; save/load; STL re-read; stale export blocked; invalid table shown')
        print('Artifacts:',out)
    finally:
        window.close(); app.processEvents()


if __name__=='__main__': main()
