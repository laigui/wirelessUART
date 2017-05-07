#!/usr/bin/python
# -*- coding: utf-8 -*-

__author__ = 'Wei'

from Tkinter import *
import Tkinter as tk
import threading
from tests.myTest import MyTest
import logging
import time


class ScrolledText(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent)
        self.text = tk.Text(self, *args, **kwargs)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        # expose some text methods as methods on this object
        self.insert = self.text.insert
        self.delete = self.text.delete
        self.mark_set = self.text.mark_set
        self.get = self.text.get
        self.index = self.text.index
        self.search = self.text.search

class inputCellE(tk.Frame):
    def __init__(self, parent, ltxt, default):
        tk.Frame.__init__(self, parent, class_='inputCellE')
        self.pack(side=TOP)
        self.creatWidget(ltxt, default)
        self.get = self.p.get

    def creatWidget(self, ltxt, default):
        self.l = Label(self, text=ltxt, width=15, anchor=E, padx=5)
        self.l.pack(side=LEFT)
        self.p = Entry(self)
        self.p.insert(1, default)
        self.p.pack(side=RIGHT)

class inputCellLB(tk.Frame):
    def __init__(self, parent, ltxt, alist):
        tk.Frame.__init__(self, parent, class_='inputCellLB')
        self.pack(side=TOP)
        self.creatWidget(ltxt, alist)
        self.get = self.p.get

    def creatWidget(self, ltxt, alist):
        self.l = Label(self, text=ltxt, width=10, anchor=E, padx=5)
        self.l.pack(side=LEFT)
        self.p = Listbox(self)
        self.p.insert(END, *alist)
        self.p.pack(side=RIGHT)

class inputCellOM(tk.Frame):
    def __init__(self, parent, ltxt, alist, default):
        tk.Frame.__init__(self, parent, class_='inputCellOM')
        self.pack(side=TOP)
        self.creatWidget(ltxt, alist, default)
        self.get = self.v.get

    def creatWidget(self, ltxt, alist, default):
        self.l = Label(self, text=ltxt, width=10, anchor=E, padx=5)
        self.l.pack(side=LEFT)
        self.v = StringVar()
        self.v.set(default)
        self.p = OptionMenu(self, self.v, *alist)
        self.p.pack(side=RIGHT)

class mainWin(tk.Frame):
    parity_list = ('NONE', 'EVEN', 'ODD', 'MARK', 'SPACE')
    stopbits_list = ('1', '1.5', '2')
    bytesize_list = ('5', '6', '7', '8')
    port_list = ['None']

    def __init__(self, parent):
        self.isSerialEnabled = False
        tk.Frame.__init__(self, parent, class_='mainWin')
        self.pack(fill=BOTH, expand=TRUE)
        self.creatWidget()

    def list_ports(self):
        import os
        if os.name == 'nt':
            from serial.tools.list_ports_windows import comports
        elif os.name == 'posix':
            from serial.tools.list_ports_posix import comports
        else:
            raise ImportError("Sorry: no implementation for your platform ('%s') available" % (os.name,))
        ports = sorted(comports())
        for n, (port, desc, hwid) in enumerate(ports, 1):
            self.port_list.append(port)

    def creatWidget(self):
        pw1 = PanedWindow(self)
        pw1.pack(fill=BOTH, expand=1)
        frameInput = LabelFrame(pw1, text="设置和控制", height=200, width=30)
        frameInput.pack(fill="both", expand="yes")
        pw1.add(frameInput)
        self.pkt_min_len = inputCellE(frameInput, "最小包长（字节）", "5")
        self.pkt_max_len = inputCellE(frameInput, "最大包长（字节）", "30")
        self.tx_interval = inputCellE(frameInput, "发送间隔（秒）", "2")
        self.rx_timeout = inputCellE(frameInput, "接收超时（秒）", "5")
        self.loop = inputCellE(frameInput, "测试循环次数", "0")

        self.text_button_start = StringVar()
        self.text_button_start.set("开始")
        self.button_en = Button(frameInput, textvariable=self.text_button_start,
                                command=do_start, bg='lightgreen',
                                activebackground='lightgreen')
        self.button_en.pack(side=TOP)

        self.text_button_stop = StringVar()
        self.text_button_stop.set("停止")
        self.button_en = Button(frameInput, textvariable=self.text_button_stop,
                                command=do_stop, bg='pink',
                                activebackground='pink')
        self.button_en.pack(side=TOP)

        pw2 = PanedWindow(pw1, orient=VERTICAL)
        pw1.add(pw2)
        frameReceived = LabelFrame(pw2, text="测试记录", width=800)
        self.text_recv = ScrolledText(frameReceived)
        self.text_recv.pack(side=TOP, fill=BOTH, expand=1)
        pw2.add(frameReceived)

    def updateRxWin(self, aStr):
        self.text_recv.insert(tk.INSERT, aStr)
        self.text_recv.text.see(tk.END)
        self.text_recv.update()

def update_GUI():
    while True:
        message = test.toGUI()
        mywin.updateRxWin(message)
        time.sleep(1)

def new_gui_thread():
    global t_gui
    t_gui = threading.Thread(target=update_GUI, name="Thread-GUI")
    t_gui.setDaemon(True)
    t_gui.start()

def do_start():
    test.configure(tx_interval=int(mywin.tx_interval.get()),
                   rx_timeout=int(mywin.rx_timeout.get()),
                   pkt_max_len=int(mywin.pkt_max_len.get()),
                   pkt_min_len=int(mywin.pkt_min_len.get()),
                   )
    global t_tx
    if t_tx == None:
        t_tx = threading.Thread(target=test.start_tx, args=[int(mywin.loop.get())], name="Thread-TX")
        t_tx.start()
        logger.info("Test started with:")
        logger.info("tx_interval: %s", mywin.tx_interval.get())
        logger.info("rx_timeout: %s", mywin.rx_timeout.get())
        logger.info("pkt_max_len: %s", mywin.pkt_max_len.get())
        logger.info("pkt_min_len: %s", mywin.pkt_min_len.get())
        logger.info("loop: %s", mywin.loop.get())

def do_stop():
    test.stop_tx()
    global t_tx
    if t_tx != None:
        t_tx.join()
        t_tx = None

def logger_init():
    global logger
    logger = logging.getLogger("myLogger")
    logger.setLevel(logging.DEBUG)
    from time import localtime, strftime
    log_filename = strftime("test-%y%m%d-%H:%M:%S.log", localtime())
    # create file handler which logs even debug messages
    fh = logging.FileHandler(log_filename)
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    # add the handlers to logger
    logger.addHandler(ch)
    logger.addHandler(fh)

if __name__ == "__main__":
    global t_tx
    t_tx = None
    logger_init()
    test = MyTest()
    rootWin = tk.Tk()
    rootWin.title('智能路灯无线通讯压力测试 V0507.1')
    mywin = mainWin(rootWin)
    new_gui_thread()
    rootWin.mainloop()

