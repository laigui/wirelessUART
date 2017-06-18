#!/usr/bin/python
#  -*- coding:utf-8 -*-

__author__ = 'Mike'

import os
try:
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.filedialog as filedialog
except:
    import Tkinter as tk
    import ttk
    import tkFileDialog as filedialog
import json
import shutil


LARGE_FONT = ("Verdana", 16)
MIDDLE_FONT = ("Verdana", 12)
LAMP_NAME = ['灯具1', '灯具2', '灯具3']
LAMP_MAX_NUM = 512


class Led(tk.Canvas):
    """ (indicator) a LED """
    # color is on_color when status is 1, off_color when status is 0 "

    def __init__(self, master, off_color="red", on_color="green", size=20, **kw):
        tk.Canvas.__init__(self, master, width=size, height=size, bd=0)
        self.off_color = off_color
        self.on_color = on_color
        self.oh = self.create_oval(1, 1, size, size)
        self.itemconfig(self.oh, fill=off_color)

    def update(self, status):
        if status == 1:
            self.itemconfig(self.oh, fill=self.on_color)
        else:
            self.itemconfig(self.oh, fill=self.off_color)


class SimpleTable(tk.Frame):
    """ Simple Table """
    def __init__(self, parent, rows=4, columns=4):
        # use black background so it "peeks through" to
        # form grid lines
        tk.Frame.__init__(self, parent, background="black")
        self._widgets = []
        for row in range(rows):
            current_row = []
            for column in range(columns):
                label = tk.Label(self, text="%s/%s" % (row, column), font=MIDDLE_FONT,
                                 borderwidth=0, width=16, height=2)
                label.grid(row=row, column=column, sticky="nsew", padx=1, pady=1)
                current_row.append(label)
            self._widgets.append(current_row)

        for column in range(columns):
            self.grid_columnconfigure(column, weight=1)


    def set(self, row, column, value):
        widget = self._widgets[row][column]
        widget.configure(text=value)


class Application(tk.Tk):
    """多页面演示程序"""

    def __init__(self):
        try:
            super().__init__()
        except TypeError:
            tk.Tk.__init__(self)

        self.wm_title("智能路灯集控 V1.1")
        self.geometry('800x480')

        try:
            if "nt" == os.name:
                self.wm_iconbitmap(bitmap="logo_48x48.ico")
            else:
                self.wm_iconbitmap(bitmap="@gui/logo_48x48.xbm")
        except tk.TclError:
            print('no icon file found')

        container = tk.Frame(self)
        container.grid(column=0, row=0)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (StartPage, PageOne, PageTwo, PageThree, PageFour):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")  # 四个页面的位置都是 grid(row=0, column=0), 位置重叠，只有最上面的可见！！

        self.frames[StartPage].grid_columnconfigure(0, weight=1, minsize=266)
        self.frames[StartPage].grid_columnconfigure(1, weight=1, minsize=266)
        self.frames[StartPage].grid_columnconfigure(2, weight=1, minsize=266)
        self.frames[StartPage].grid_rowconfigure(2, weight=1, minsize=120)
        self.frames[StartPage].grid_rowconfigure(3, weight=1, minsize=120)
        self.frames[StartPage].grid_rowconfigure(4, weight=1, minsize=120)

        self.frames[PageOne].grid_columnconfigure(0, weight=1)
        self.frames[PageOne].grid_columnconfigure(1, weight=1)
        self.frames[PageOne].grid_columnconfigure(2, weight=10)
        for row in range(len(LAMP_NAME)):
            self.frames[PageOne].grid_rowconfigure(row, weight=1)
        self.frames[PageOne].grid_rowconfigure(len(LAMP_NAME), weight=10)

        self.show_frame(StartPage)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()  # 切换，提升当前 tk.Frame z轴顺序（使可见）！！此语句是本程序的点睛之处

    def on_all_lamps_on_button_click(self):
        """灯具全部开"""
        pass

    def on_all_lamps_off_button_click(self):
        '''灯具全部关'''
        pass

    def on_lamp_status_query_button_click(self, lamp_num):
        """灯具状态查询"""
        print("Lamp #" + str(lamp_num) + " status query on-going")
        pass

    def on_lamp_status_set_button_click(self, lamp_num):
        """灯具状态设置"""
        print("Lamp #" + str(lamp_num) + " status set on-going")
        pass

    def on_lamp_set_slider_move(self, value, lamp_num):
        """灯具状态设置"""
        print("Lamp #" + str(lamp_num) + "  " + str(value) + " slider set on-going")
        pass

    def on_lamp_status_set_checkbutton_click(self, lamp_num, status):
        """维修模式灯具状态设计"""
        print("Lamp #" + str(lamp_num) + " checkbotton status = " + str(status))
        pass

    def on_lamp_indicator_update(self, lamp_num, status):
        """状态查询更新灯具状态"""
        self.frames[PageOne].leds[lamp_num-1].update(status)

    def on_lamp_confirm_button_click(self):
        """维修模式灯具确认"""
        print(str(self.frames[PageThree].var1.get()) + " slider set on-going")
        print(str(self.frames[PageThree].var2.get()) + " slider set on-going")
        pass


class StartPage(tk.Frame):
    """主页"""

    def __init__(self, parent, root):
        try:
            super().__init__(parent)
        except TypeError:
            tk.Frame.__init__(self)

        s = ttk.Style()
        s.configure("BIG.TButton", foreground="black", background="white", font=LARGE_FONT, width=12, padding=18)
        s.map("BIG.TButton",
            foreground=[('disabled', 'grey'),
                      ('pressed', 'red'),
                      ('active', 'blue')],
            background=[('disabled', 'magenta'),
                      ('pressed', '!focus', 'cyan'),
                      ('active', 'green')],
            highlightcolor=[('focus', 'green'),
                          ('!focus', 'red')],
            relief=[('pressed', 'groove'),
                  ('!pressed', 'ridge')])

        filename = 'gui/logo.gif'
        try:
            img = tk.PhotoImage(file=filename)
        except:
            print('no gif logo file found')
        img = img.subsample(3)
        label1 = ttk.Label(self, image=img)
        label1.image = img
        label2 = ttk.Label(self, text='江苏天恒智能科技出品', font=MIDDLE_FONT, padding=10)

        button1 = ttk.Button(self, text="灯具全部开", style="BIG.TButton", command=root.on_all_lamps_on_button_click)
        button2 = ttk.Button(self, text="灯具全部关", style="BIG.TButton", command=root.on_all_lamps_off_button_click)
        button3 = ttk.Button(self, text="灯具状态查询", style="BIG.TButton", state="enabled",
                             command=lambda: root.show_frame(PageOne))
        button4 = ttk.Button(self, text="节能模式一", style="BIG.TButton", state="disabled")
        button5 = ttk.Button(self, text="节能模式二", style="BIG.TButton", state="disabled")
        button6 = ttk.Button(self, text="节能模式三", style="BIG.TButton", state="disabled")
        button7 = ttk.Button(self, text="环境数据检测", style="BIG.TButton", state="disabled",
                             command=lambda: root.show_frame(PageTwo))
        button8 = ttk.Button(self, text="系统网络设定", style="BIG.TButton", command=lambda: root.show_frame(PageFour))
        button9 = ttk.Button(self, text="维修模式", style="BIG.TButton", command=lambda: root.show_frame(PageThree))

        label1.grid(column=1, row=1)
        label2.grid(column=1, row=0)
        button1.grid(column=0, row=2)
        button2.grid(column=1, row=2)
        button3.grid(column=2, row=2)
        button4.grid(column=0, row=3)
        button5.grid(column=1, row=3)
        button6.grid(column=2, row=3)
        button7.grid(column=0, row=4)
        button8.grid(column=1, row=4)
        button9.grid(column=2, row=4)


class PageOne(tk.Frame):
    """灯具状态查询页面"""

    def __init__(self, parent, root):
        try:
            super().__init__(parent)
        except TypeError:
            tk.Frame.__init__(self)

        self.leds = []
        self.col_num = 30
        self.row_pixel = 20
        self.row_offset = 30
        self.col_offset = 100

        for n in range(LAMP_MAX_NUM):
            self.leds.append(Led(self))
            self.leds[n].place(x=self.col_offset+n%self.col_num*self.row_pixel,
                               y=self.row_offset+n//self.col_num*self.row_pixel)

        button0 = ttk.Button(self, text="回到主页", style="BIG.TButton", command=lambda: root.show_frame(StartPage)) \
            .place(x=300, y=380)


class PageTwo(tk.Frame):
    """环境数据检测页面"""

    def __init__(self, parent, root):
        try:
            super().__init__(parent)
        except TypeError:
            tk.Frame.__init__(self)

        self.buttons = []

        for n in range(len(LAMP_NAME)):
            # create buttons for each lamps
            self.buttons.append(ttk.Button(self, text=LAMP_NAME[n], style="Lamp.TButton"))
            self.buttons[n].grid(row=n, column=0, padx=10, pady=10)

        button0 = ttk.Button(self, text="回到主页", style="BIG.TButton", command=lambda: root.show_frame(StartPage))\
            .place(x=300, y=350)


class PageThree(tk.Frame):
    """维修模式"""

    def __init__(self, parent, root):
        try:
            super().__init__(parent)
        except TypeError:
            tk.Frame.__init__(self)

        s = ttk.Style()
        s.configure("MID.TButton", foreground="black", background="white", font=MIDDLE_FONT, width=10, padding=12)
        s.map("MID.TButton",
                  foreground=[('disabled', 'grey'),
                              ('pressed', 'red'),
                              ('active', 'blue')],
                  background=[('disabled', 'magenta'),
                              ('pressed', '!focus', 'cyan'),
                              ('active', 'green')],
                  highlightcolor=[('focus', 'green'),
                                  ('!focus', 'red')],
                  relief=[('pressed', 'groove'),
                          ('!pressed', 'ridge')])

        self.label1 = ttk.Label(self, text="该组节点数为:", font=LARGE_FONT)
        self.label1.place(x=10, y=10)
        self.lamp_num = tk.StringVar()
        self.label2 = ttk.Label(self, textvariable=self.lamp_num, font=LARGE_FONT)
        self.label2.place(x=150, y=10)
        self.label3 = ttk.Label(self, text="节点号", font=LARGE_FONT)
        self.label3.place(x=10, y=70)
        self.spinboxes = []
        for n in range(3):
            self.spinboxes.append(tk.Spinbox(self, from_=0, to=9, font=("Verdana", 30), width=3))
            self.spinboxes[n].place(x=100+n*120, y=60)
        self.label4 = ttk.Label(self, text="调光1", font=LARGE_FONT)
        self.label4.place(x=500, y=50)
        self.label5 = ttk.Label(self, text="调光2", font=LARGE_FONT)
        self.label5.place(x=500, y=100)

        self.var1 = tk.IntVar()
        self.progbar1 = tk.Scale(self, from_=0, to=100, orient='horizontal', resolution=1, width=20,
                                 length=200, variable=self.var1)
        self.progbar1.place(x=560, y=30)
        self.var2 = tk.IntVar()
        self.progbar2 = tk.Scale(self, from_=0, to=100, orient='horizontal', resolution=1, width=20,
                                 length=200, variable=self.var2)
        self.progbar2.place(x=560, y=80)

        button1 = ttk.Button(self, text="确定", style="MID.TButton", command=root.on_lamp_confirm_button_click)\
            .place(x=400, y=150, anchor=tk.CENTER)
        t = SimpleTable(self, 3, 4)
        t.place(x=70, y=200)
        t.set(0, 0, '工作状态')
        t.set(0, 2, '工作电流')
        t.set(1, 0, '工作电压')
        t.set(1, 2, '电网频率')
        t.set(2, 0, '有效功率')
        t.set(2, 2, 'CO2排放量')
        # self.labels = []
        # self.checks = []
        # self.progbars = []
        # v0 = tk.IntVar()
        # v1 = tk.IntVar()
        # v2 = tk.IntVar()
        #
        # s = ttk.Style()
        # s.configure("CB.Toolbutton", foreground="black", background="white", width=6, padding=6)
        #
        # for n in range(len(LAMP_NAME)):
        #     # create label, checkbotton & progressbar widgets for each lamps
        #     self.labels.append(ttk.Label(self, text=LAMP_NAME[n]))
        #     self.labels[n].grid(row=n, column=0, padx=10, pady=10)
        #     self.checks.append(ttk.Checkbutton(self, text=' 开关 ', style='CB.Toolbutton', command=lambda: root.on_lamp_status_set_checkbutton_click(n)))
        #     self.checks[n].grid(row=n, column=1, padx=10, pady=10)
        #     self.progbars.append(ttk.Scale(self, from_=0, to=100, orient="horizontal",
        #                      command=lambda x,y=1: root.on_lamp_set_slider_move(x,y)))
        #     self.progbars[n].grid(row=n, column=2)
        #
        # self.checks[0].configure(variable=v0, command=lambda: root.on_lamp_status_set_checkbutton_click(0, v0.get()))
        # self.checks[1].configure(variable=v1, command=lambda: root.on_lamp_status_set_checkbutton_click(1, v1.get()))
        # self.checks[2].configure(variable=v2, command=lambda: root.on_lamp_status_set_checkbutton_click(2, v2.get()))

        button0 = ttk.Button(self, text="回到主页", style="BIG.TButton", command=lambda: root.show_frame(StartPage)) \
            .place(x=300, y=350)


class PageFour(tk.Frame):
    """系统网络设定"""

    def __init__(self, parent, root):
        try:
            super().__init__(parent)
        except TypeError:
            tk.Frame.__init__(self)

        self.v = tk.StringVar()
        entry = ttk.Entry(self, width=80, textvariable=self.v)
        entry.pack(side="top", anchor="center", pady=10)

        def callback():
            entry.delete(0, "end")  # 清空entry里面的内容
            # 调用filedialog模块的askdirectory()函数去打开文件夹
            filename = filedialog.askopenfilename()
            if filename:
                entry.insert(0, filename)  # 将选择好的文件加入到entry里面

        button1 = ttk.Button(self, text="打开配置文件", style="MID.TButton", command=callback)
        button1.pack(side="top", anchor="center", pady=10)

        button2 = ttk.Button(self, text="加载配置", style="MID.TButton",
                             command=lambda: self.load_user_config_file(parent, root))
        button2.pack(side="top", anchor="center")

        button3 = ttk.Button(self, text="导出日志", style="MID.TButton",
                             command=self.save_log_file)
        button3.pack(side="top", anchor="center", pady=50)

        button0 = ttk.Button(self, text="回到主页", style="BIG.TButton",
                             command=lambda: root.show_frame(StartPage))
        button0.place(x=300, y=350)

    def load_user_config_file(self, parent, root):
        """加载用户配置文件"""
        try:
            with open(self.v.get()) as f_obj:
                data = json.load(f_obj)
            print("Config file " + self.v.get() + " is loaded!")
            root.frames[PageThree].lamp_num.set(data['lamp_num'])
        except IOError:
            print("Config file " + self.v.get() + " cannot find!")

    def get_latest_log_file(self):
        base_dir = '.'
        #列出目录下文件
        list = os.listdir(base_dir)
        #排序
        try:
            file=sorted(
                [
                    (x, os.path.getctime(os.path.join(base_dir, x)))  # 生成一个列表，列表的每个元素是一个元组（文件，文件创建时间）
                    for x in list if os.path.isfile(os.path.join(base_dir, x)) and os.path.splitext(x)[1] == '.log'  # p是文件夹路径，对p下的所有内容，只将文件的信息加入列表
                ],
                key=lambda i: i[1])[-1]  # 对列表进行排序，排序的依据是每一个元组元素的第二个元素，排序后取最后一个元素
            return file[0]
        except IndexError:
            print("no such file in base folder!")
            return 'null'

    def save_log_file(self):
        src = self.get_latest_log_file()
        dest = '/media/pi/265B-0F19/znlg_log.txt'
        try:
            shutil.copy(src, dest)
            print("Copied from " + src + " to " + dest)
        except:
            print("Destination " + dest + " open failed!")


if __name__ == '__main__':
    # 实例化Application
    app = Application()

    # 主消息循环:
    app.mainloop()
