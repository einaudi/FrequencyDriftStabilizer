# -*- coding: utf-8 -*-

import time
import numpy as np

from PyQt5.QtWidgets import (
    QMessageBox,
    QProgressDialog
)


def dialogWarning(msg):
    msgBox = QMessageBox()
    msgBox.setText(msg)
    msgBox.setIcon(QMessageBox.Warning)
    msgBox.exec()


def dialogInformation(msg):
    msgBox = QMessageBox()
    msgBox.setText(msg)
    msgBox.exec()

def dialogFileExists():
    msgBox = QMessageBox()
    msgBox.setText('File already exists!')
    msgBox.setInformativeText('Do you wish to overwrite it?')
    msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msgBox.setDefaultButton(QMessageBox.No)
    msgBox.setIcon(QMessageBox.Question)

    return msgBox.exec()
