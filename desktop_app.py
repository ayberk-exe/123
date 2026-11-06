"""MarineProp Studio native desktop entrypoint; no Streamlit or browser server."""
import argparse
import os
import sys


def main():
    parser=argparse.ArgumentParser(description='MarineProp Studio v0.2 native designer')
    parser.add_argument('--offscreen',action='store_true',help='Headless Qt/VTK verification, not a Windows GUI validation')
    args=parser.parse_args()
    if args.offscreen:
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        os.environ.setdefault('PYVISTA_OFF_SCREEN','true')
    from PySide6.QtWidgets import QApplication
    from marineprop.desktop.window import PropellerWindow
    application=QApplication(sys.argv[:1])
    application.setApplicationName('MarineProp Studio')
    window=PropellerWindow(offscreen=args.offscreen)
    window.show()
    return application.exec()


if __name__=='__main__':
    raise SystemExit(main())
