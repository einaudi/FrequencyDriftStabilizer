# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QLabel,
    QCheckBox,
    QComboBox,
    QProgressBar,
    QTextEdit,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QGroupBox
)
import pyqtgraph as pg
from widgets.FiltersWidget import FiltersWidget
from widgets.LedIndicatorWidget import LedIndicator


# ----- WIDGETS -----
def generate_widgets(widget_conf):

    ret = {}

    for widget_type in widget_conf:
            for widget in widget_conf[widget_type]:
                if widget_type == 'QWidget':
                    tmp = QWidget()
                elif widget_type == 'QLineEdit':
                    tmp = QLineEdit()
                    if 'default' in widget.keys():
                        tmp.setText(widget['default'])
                    if 'readOnly' in widget.keys():
                        tmp.setReadOnly(widget['readOnly'])
                elif widget_type == 'QPushButton':
                    tmp = QPushButton(widget['label'])
                elif widget_type == 'QCheckBox':
                    tmp = QCheckBox()
                    if 'default' in widget.keys():
                        tmp.setChecked(widget['default'])
                elif widget_type == 'QComboBox':
                    tmp = QComboBox()
                    if 'contents' in widget.keys():
                        for item in widget['contents']:
                            tmp.addItem(item)
                elif widget_type == 'QProgressBar':
                    tmp = QProgressBar()
                elif widget_type == 'QTextEdit':
                    tmp = QTextEdit()
                    if 'default' in widget.keys():
                        tmp.setText(widget['default'])
                    if 'readOnly' in widget.keys():
                        tmp.setReadOnly(widget['readOnly'])
                elif widget_type == 'QLabel':
                    tmp = QLabel(widget['label'])
                elif widget_type == 'PlotWidget':
                    tmp = pg.PlotWidget()
                elif widget_type == 'FiltersWidget':
                    tmp = FiltersWidget()
                elif widget_type == 'LedIndicator':
                    tmp = LedIndicator()
                else:
                    print('Unknown widget type {}!'.format(widget_type))
                    quit()

                ret[widget['name']] = tmp
    
    return ret


# ----- LAYOUT -----
def generate_layout(layout_conf, widgets):

    layouts = {}

    # Generate sub-layouts
    for layout in layout_conf['layouts']:
            if layout['type'] == 'QGridLayout':
                tmp = QGridLayout()
                for widget in layout['widgets']:
                    if 'span' in widget.keys():
                        spanRow = widget['span'][0]
                        spanCol = widget['span'][1]
                    else:
                        spanRow = 1
                        spanCol = 1
                    if widget['type'] == 'QLabel':
                        tmp.addWidget(
                            QLabel(widget['label']),
                            widget['position'][0],
                            widget['position'][1],
                            spanRow,
                            spanCol
                        )
                    else:
                        tmp.addWidget(
                            widgets[widget['name']],
                            widget['position'][0],
                            widget['position'][1],
                            spanRow,
                            spanCol
                        )
            elif layout['type'] == 'QHBoxLayout':
                tmp = QHBoxLayout()
                for widget in layout['widgets']:
                    if widget['type'] == 'QLabel':
                        spam = QLabel(widget['label'])
                    elif widget['type'] == 'stretch':
                        tmp.addStretch(widget['value'])
                        continue
                    else:
                        spam = widgets[widget['name']]
                    if 'stretch' in widget.keys():
                        stretch = widget['stretch']
                    else:
                        stretch = 0
                    tmp.addWidget(spam, stretch=stretch)
            elif layout['type'] == 'QVBoxLayout':
                tmp = QVBoxLayout()
                for widget in layout['widgets']:
                    if widget['type'] == 'QLabel':
                        spam = QLabel(widget['label'])
                    elif widget['type'] == 'stretch':
                        tmp.addStretch(widget['value'])
                        continue
                    else:
                        spam = widgets[widget['name']]
                    tmp.addWidget(spam)
            layouts[layout['name']] = tmp

    mainLayout = generate_layout_tree(layout_conf['mainLayout'], layouts, widgets)

    return mainLayout

def generate_layout_tree(layoutTree, layouts, widgets):
    
    if layoutTree['type'] == 'QHBoxLayout':
        ret = QHBoxLayout()
    elif layoutTree['type'] == 'QVBoxLayout':
        ret = QVBoxLayout()
    elif layoutTree['type'] == 'QGroupBox':
        ret = QGroupBox(layoutTree['label'])
    elif layoutTree['type'] == 'layout':
        ret = layouts[layoutTree['name']]
    elif layoutTree['type'] == 'widget':
        return widgets[layoutTree['name']]
    else:
        print('Unknown layout type {}!'.format(layoutTree['type']))
        quit()

    if layoutTree['contents']:
        for item in layoutTree['contents']:
            tmp = generate_layout_tree(item, layouts, widgets)
            if 'stretch' in item.keys():
                stretch = item['stretch']
            else:
                stretch = 0

            try:
                ret.addLayout(tmp, stretch=stretch)
            except TypeError:
                ret.addWidget(tmp, stretch=stretch)
            except AttributeError:
                ret.setLayout(tmp)

    return ret