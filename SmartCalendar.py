import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
from datetime import datetime
import calendar
import json
import os
from wxauto import * 

from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import Tool
import functools

DATA_FILE = "calendar_events.json"
COLORS = {
    "event_day": "#FF9999",
    "current_day": "#99CCFF",
    "normal_day": "#FFFFFF"
}


@tool
def add_schedule(start_time : str, description : str) -> str: 
    """ 新增日程，比如2024-05-03 20:00:00, 周会 """

    print(start_time,description)
    date = start_time.split()[0]
    time = start_time.split()[1]

    app.add_one_event(date,time,description)

        
    return "true"

class CalendarApp:
    def __init__(self, root):
        self.root = root
        self.root.title("智能日历管理系统V1")
        self.root.geometry("800x680")
        
        self.events = self.load_events()
        self.current_date = datetime.now()
        self.selected_date = None
        
            # 添加样式配置
        style = ttk.Style()
        style.configure('Fixed.TFrame', background='#F0F0F0')
        style.configure('Narrow.TEntry', padding=3)
        style.configure('Small.TButton', padding=2)
         

        self.create_widgets()
        self.update_calendar()
        self.init_agent()

    def add_one_event(self,date,time,desc):

        event_list = self.events.get(date, [])
        
        # # 添加事件
        event_list.append({
            "time": time,
            "description": desc
        })
        event_list.sort(key=lambda x: x["time"])
        self.events[date] = event_list
        self.save_events()
        self.update_calendar()

    def create_widgets(self):
        # 主界面布局
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        
        # 左侧问答面板 (核心修复)
        qa_frame = ttk.Frame(main_paned, width=250)
        qa_frame.pack_propagate(False)  # 禁止子组件改变框架尺寸
        self.create_qa_interface(qa_frame)
        main_paned.add(qa_frame, weight=0)  # weight=0 表示不拉伸
        
        # 主内容区域
        main_content = ttk.Frame(main_paned)
        self.create_main_content(main_content)
        main_paned.add(main_content, weight=1)  # weight=1 自动填充剩余空间

    def create_main_content(self, parent):
        """创建主要内容区域（日历+事件）"""
        content_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        content_paned.pack(fill=tk.BOTH, expand=True)
        
        # 日历区域
        cal_frame = ttk.Frame(content_paned)
        self.create_calendar_interface(cal_frame)
        content_paned.add(cal_frame)
        
        # 事件区域
        event_frame = ttk.Frame(content_paned, height=200)
        self.create_event_interface(event_frame)
        content_paned.add(event_frame)
    
    def create_calendar_interface(self, parent):
        """创建日历界面"""
        # 控制栏
        control_frame = ttk.Frame(parent)
        control_frame.pack(pady=10, fill=tk.X)
        
        self.month_var = tk.StringVar()
        self.year_var = tk.StringVar()
        
        ttk.Button(control_frame, text="←", command=self.prev_month).pack(side=tk.LEFT, padx=5)
        self.month_combo = ttk.Combobox(control_frame, 
                                      textvariable=self.month_var,
                                      values=list(calendar.month_name[1:]),
                                      state="readonly")
        self.month_combo.pack(side=tk.LEFT, padx=5)
        
        self.year_combo = ttk.Combobox(control_frame, 
                                     textvariable=self.year_var,
                                     values=[str(y) for y in range(2000, 2031)],
                                     width=5)
        self.year_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="→", command=self.next_month).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="添加事件", 
                 command=self.add_event).pack(side=tk.RIGHT, padx=5)
        
        # 日历显示区域
        self.cal_frame = ttk.Frame(parent)
        self.cal_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def create_event_interface(self, parent):
        """创建事件列表界面"""
        event_container = ttk.LabelFrame(parent, text="当日事件")
        event_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.event_list = tk.Listbox(event_container,font=('微软雅黑', 50))
        self.event_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        btn_frame = ttk.Frame(event_container)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="删除选中", 
                 command=self.delete_event).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="刷新", 
                 command=self.update_calendar).pack(side=tk.RIGHT)
    
    def create_qa_interface(self, parent):
        """创建问答界面 (宽度固定版)"""
        parent.config(width=250)  # 显式设置宽度
        
        qa_frame = ttk.LabelFrame(parent, text="智能助手")
        qa_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # 对话历史区域
        self.chat_history = scrolledtext.ScrolledText(
            qa_frame,
            wrap=tk.WORD,
            width=20,  # 按字符数控制宽度
            font=('微软雅黑', 8),
            state='disabled'
        )
        self.chat_history.pack(fill=tk.BOTH, expand=True)
            # 使用网格布局确保组件可见

        input_frame = ttk.Frame(qa_frame)
        input_frame.pack(fill=tk.BOTH, padx=5, pady=5)  # 改为BOTH填充
        
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)

        # 将单行输入框改为多行文本输入
        self.user_input = tk.Text(
            input_frame,
            height=8,  # 高度增加3倍（原单行输入框等效高度约1.3行）
            wrap=tk.WORD,
            font=('微软雅黑', 9),
            padx=5,
            pady=5
        )
        self.user_input.grid(row=0, column=0, sticky="nsew")
        
        # 发送按钮容器（保持垂直居中）
        btn_container = ttk.Frame(input_frame)
        btn_container.grid(row=0, column=1, sticky="ns", padx=1)

         # 垂直排列的发送按钮
        send_btn = ttk.Button(
            btn_container,
            text="发\n送",  # 添加换行符实现垂直文字
            command=self.process_query,
            width=3
        )
        send_btn.pack(fill=tk.BOTH, expand=True, pady=2)

        # 绑定回车键（适应多行输入）
        self.user_input.bind("<Return>", self.handle_input_return)

            # 新增按钮区域
        button_frame = ttk.Frame(qa_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 获取微信消息
        ttk.Button(button_frame, text="获取微信消息",
                command=self.get_wx_msg).pack(side=tk.LEFT)
        # 清空历史按钮
        ttk.Button(button_frame, text="清空历史",
                command=self.clear_chat_history).pack(side=tk.LEFT)
        
        # 示例功能按钮（可根据需要修改）
        ttk.Button(button_frame, text="帮助",
                command=self.show_help).pack(side=tk.RIGHT)

    def get_wx_msg(self):
        def is_valid_time(time_str: str) -> bool:
            """
            尝试通过 datetime 解析时间（允许灵活格式需调整）
            """
            try:
                datetime.strptime(time_str, "%H:%M:%S")
                return True
            except ValueError:
                return False
        
        def get_more_messages(wx,name):
            wx.ChatWith(name)
            wx.rollToTop()
            msgs = wx.GetAllMessage()
            msg_list = []
            switch =False
            for msg in msgs:
                if switch:
                    print('%s : %s' % (msg[0], msg[1]))
                    msg_list.append(msg[0]+ msg[1])
                    if(msg[0]!='SYS'):
                        self.user_input.insert(tk.END,msg[0]+msg[1]+'\n') 
                else:
                    switch = is_valid_time(msg[1])
            return msg_list
        msgs_list=[]
        wx = WeChat()
        name_list = wx.GetAllSessionList()
        for name in name_list:
            msgs_list.append(get_more_messages(wx, name))
        


    def clear_chat_history(self):
        """清空对话历史"""
        self.chat_history.configure(state='normal')
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.configure(state='disabled')

    def show_help(self):
        """显示帮助信息（示例功能）"""
        help_text = """使用说明：
    1. 输入自然语言查询事件
    2. 点击日期查看详细安排
    3. 支持时间冲突检测
    4. 可语音查询近期安排"""
        self._add_message(f"助手：{help_text}", "system")


    def create_event_interface(self, parent):
        """创建事件列表界面"""
        self.event_list = tk.Listbox(parent)
        self.event_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="删除选中", 
                 command=self.delete_event).pack(side=tk.LEFT)
            # 新增修改按钮
        ttk.Button(btn_frame, text="修改事件",
             command=self.modify_event).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="刷新", 
                 command=self.update_calendar).pack(side=tk.RIGHT)
    def modify_event(self):
        """修改选中事件"""
        if not self.selected_date:
            messagebox.showwarning("提示", "请先选择要修改的日期")
            return
        
        selection = self.event_list.curselection()
        if not selection:
            messagebox.showwarning("提示", "请选择要修改的事件")
            return
        
        try:
            # 获取原始事件信息
            original_event = self.events[self.selected_date][selection[0]]
            
            # 创建修改对话框
            dialog = tk.Toplevel(self.root)
            dialog.title("修改事件")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # 日期输入
            ttk.Label(dialog, text="日期 (YYYY-MM-DD):").grid(row=0, column=0, padx=5, pady=5)
            date_entry = ttk.Entry(dialog)
            date_entry.grid(row=0, column=1, padx=5, pady=5)
            date_entry.insert(0, self.selected_date)
            
            # 时间输入
            ttk.Label(dialog, text="时间 (HH:MM:SS):").grid(row=1, column=0, padx=5, pady=5)
            time_entry = ttk.Entry(dialog)
            time_entry.grid(row=1, column=1, padx=5, pady=5)
            time_entry.insert(0, original_event["time"])
            
            # 描述输入
            ttk.Label(dialog, text="事件描述:").grid(row=2, column=0, padx=5, pady=5)
            desc_entry = ttk.Entry(dialog)
            desc_entry.grid(row=2, column=1, padx=5, pady=5)
            desc_entry.insert(0, original_event["description"])
            
            def on_confirm():
                # 获取输入值
                new_date = date_entry.get().strip()
                new_time = time_entry.get().strip()
                new_desc = desc_entry.get().strip()
                
                # 验证输入
                if not all([new_date, new_time, new_desc]):
                    messagebox.showerror("错误", "所有字段必须填写")
                    return
                    
                if not self.validate_date(new_date):
                    messagebox.showerror("错误", "无效日期格式")
                    return
                    
                if not self.validate_time(new_time):
                    messagebox.showerror("错误", "无效时间格式")
                    return
                
                # 检查时间冲突（排除自身）
                if new_date == self.selected_date:
                    events = [e for idx, e in enumerate(self.events[self.selected_date]) 
                            if idx != selection[0]]
                else:
                    events = self.events.get(new_date, [])
                    
                if any(e["time"] == new_time for e in events):
                    messagebox.showerror("错误", "目标时间已有安排")
                    return
                    
                # 执行修改
                try:
                    # 删除原事件
                    del self.events[self.selected_date][selection[0]]
                    if not self.events[self.selected_date]:
                        del self.events[self.selected_date]
                    
                    # 添加新事件
                    self.events.setdefault(new_date, []).append({
                        "time": new_time,
                        "description": new_desc
                    })
                    self.events[new_date].sort(key=lambda x: x["time"])
                    
                    self.save_events()
                    self.update_calendar()
                    dialog.destroy()
                    
                    # 如果修改了日期，需要更新选中日期
                    if new_date != self.selected_date:
                        year, month, day = map(int, new_date.split('-'))
                        self.current_date = datetime(year, month, 1)
                        self.selected_date = new_date
                        self.update_calendar()
                    
                    self.show_events(int(new_date.split('-')[2]))
                except Exception as e:
                    messagebox.showerror("错误", f"修改失败: {str(e)}")
            
            ttk.Button(dialog, text="确认修改", command=on_confirm).grid(row=3, columnspan=2, pady=10)
            
            # 居中对话框
            dialog.update_idletasks()
            width = dialog.winfo_width()
            height = dialog.winfo_height()
            x = (dialog.winfo_screenwidth() // 2) - (width // 2)
            y = (dialog.winfo_screenheight() // 2) - (height // 2)
            dialog.geometry(f"+{x}+{y}")
            
        except Exception as e:
            messagebox.showerror("错误", f"获取事件失败: {str(e)}")
    def create_control_bar(self, parent):
        """创建控制栏"""
        control_frame = ttk.Frame(parent)
        control_frame.pack(pady=10, fill=tk.X)
        
        self.month_var = tk.StringVar()
        self.year_var = tk.StringVar()
        
        ttk.Button(control_frame, text="←", command=self.prev_month).pack(side=tk.LEFT, padx=5)
        self.month_combo = ttk.Combobox(control_frame, 
                                      textvariable=self.month_var,
                                      values=list(calendar.month_name[1:]),
                                      state="readonly")
        self.month_combo.pack(side=tk.LEFT, padx=5)
        
        self.year_combo = ttk.Combobox(control_frame, 
                                     textvariable=self.year_var,
                                     values=[str(y) for y in range(2000, 2031)],
                                     width=5)
        self.year_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="→", command=self.next_month).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="添加事件", 
                 command=self.add_event).pack(side=tk.RIGHT, padx=5)
        
        self.cal_frame = ttk.Frame(parent)
        self.cal_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    def handle_input_return(self, event):
        """处理多行输入的回车键"""
        if not event.state:  # 普通回车键
            self.process_query()
            return "break"  # 阻止默认换行
        # 允许Shift+Enter换行
        return None
    def process_query(self):
        """处理用户查询"""
        question = self.user_input.get("1.0", "end-1c").strip()  # 获取多行文本
        if not question:
            return
        
        self._add_message(f"您：{question}", "user")
        answer = self.mock_qa_engine(question)
        self._add_message(f"助手：{answer}", "bot") 
        self.user_input.delete("1.0", tk.END)  # 清空输入框
 
    def mock_qa_engine(self, question):
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        res = self.agent_executor.invoke(
                {
                    "input": question,
                    "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                #config={"callbacks": [ConsoleCallbackHandler()]}
            )
        
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return res["output"]
    
    def generate_answer(self, question):
        """生成回答的核心逻辑"""
        question = question.lower()
        
        # 今天的事件查询
        if "今天" in question and ("安排" in question or "事件" in question):
            today = datetime.now().strftime("%Y-%m-%d")
            return self._get_date_events(today)
        
        # 指定日期事件查询
        if "事件" in question and ("号" in question or "日" in question):
            date_str = self._extract_date_from_question(question)
            if date_str:
                return self._get_date_events(date_str)
            return "请提供有效的日期信息，例如：'5号有什么安排？'"
        
        # 近期事件查询
        if "近期" in question or "最近" in question:
            days = 7
            if "三天" in question:
                days = 3
            elif "一周" in question:
                days = 7
            return self._get_recent_events(days)
        
        # 事件统计
        if "统计" in question or "多少" in question:
            return f"当前共有 {len(self.events)} 个日期记录了事件，总计 {sum(len(v) for v in self.events.values())} 条事件"
        
        # 默认回复
        return "我可以帮助您查询日历事件，请尝试以下问法：\n- 今天有什么安排？\n- 5号有什么事件？\n- 最近三天有什么安排？"
    
    def _get_date_events(self, date_str):
        """获取指定日期事件"""
        if date_str in self.events:
            events = "\n".join([f"{e['time']} {e['description']}" 
                              for e in self.events[date_str]])
            return f"{date_str} 的安排：\n{events}"
        return "该日期没有安排事件"
    
    def _get_recent_events(self, days=7):
        """获取近期事件"""
        today = datetime.now()
        result = []
        for i in range(days):
            date = today.replace(day=today.day+i)
            date_str = date.strftime("%Y-%m-%d")
            if date_str in self.events:
                events = "\n".join([f"{e['time']} {e['description']}" 
                                  for e in self.events[date_str]])
                result.append(f"{date_str}：\n{events}")
        return "近期安排：\n" + "\n\n".join(result) if result else "近期没有安排"
    
    def _extract_date_from_question(self, question):
        """从问题中提取日期"""
        try:
            day = int(''.join(filter(str.isdigit, question)))
            month = self.current_date.month
            year = self.current_date.year
            return f"{year}-{month:02d}-{day:02d}"
        except:
            return None
    
    def _add_message(self, message, sender):
        """添加消息到对话历史"""
        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, message + "\n\n")
        self.chat_history.configure(state='disabled')
        self.chat_history.see(tk.END)
    

    def update_calendar(self):
        """更新日历显示"""
        # 清空旧日历
        for widget in self.cal_frame.winfo_children():
            widget.destroy()
        
        # 设置当前年月
        year = self.current_date.year
        month = self.current_date.month
        self.month_var.set(calendar.month_name[month])
        self.year_var.set(str(year))
        
        # 生成日历数据
        cal = calendar.monthcalendar(year, month)
        today = datetime.now().day if datetime.now().month == month and datetime.now().year == year else None
        
        # 创建表头
        headers = [ "一", "二", "三", "四", "五", "六","日"]
        for col, header in enumerate(headers):
            ttk.Label(self.cal_frame, text=header,anchor="center",
                     relief="ridge", width=10).grid(row=0, column=col, sticky="nsew")
        
        # 填充日期按钮
        for week_num, week in enumerate(cal, start=1):
            for day_num, day in enumerate(week):
                if day == 0:
                    continue
                
                btn = tk.Button(self.cal_frame, text=str(day),
                                relief="ridge",
                                command=lambda d=day: self.show_events(d),
                                bg=self.get_day_color(day, month, year))
                btn.grid(row=week_num, column=day_num, sticky="nsew")
                
                # 标记今天
                if day == today:
                    btn.config(bd=3, relief="sunken")
        
        # 设置网格等宽
        for col in range(7):
            self.cal_frame.grid_columnconfigure(col, weight=1)
    
    def get_day_color(self, day, month, year):
        """获取日期背景颜色"""
        date_str = f"{year}-{month:02d}-{day:02d}"
        if date_str in self.events:
            return COLORS["event_day"]
        if day == datetime.now().day and month == datetime.now().month and year == datetime.now().year:
            return COLORS["current_day"]
        return COLORS["normal_day"]
    
    def show_events(self, day):
        """显示选定日期的事件"""
        month = self.current_date.month
        year = self.current_date.year
        self.selected_date = f"{year}-{month:02d}-{day:02d}"
        
        self.event_list.delete(0, tk.END)
        if self.selected_date in self.events:
            for event in self.events[self.selected_date]:
                self.event_list.insert(tk.END, f"{event['time']} - {event['description']}")
    
    def add_event(self):
        """添加事件（整合式对话框版本）"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加新事件")
        dialog.transient(self.root)
        dialog.grab_set()

        # 创建输入组件
        ttk.Label(dialog, text="日期 (YYYY-MM-DD):").grid(row=0, column=0, padx=5, pady=5)
        date_entry = ttk.Entry(dialog)
        date_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="时间 (HH:MM:SS):").grid(row=1, column=0, padx=5, pady=5)
        time_entry = ttk.Entry(dialog)
        time_entry.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="事件描述:").grid(row=2, column=0, padx=5, pady=5)
        desc_entry = ttk.Entry(dialog)
        desc_entry.grid(row=2, column=1, padx=5, pady=5)

        # 设置默认值
        if self.selected_date:
            date_entry.insert(0, self.selected_date)
        else:
            date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        time_entry.insert(0, datetime.now().strftime("%H:%M:%S"))

        def on_confirm():
            # 获取输入值
            date_str = date_entry.get().strip()
            time_str = time_entry.get().strip()
            description = desc_entry.get().strip()

            # 输入验证
            if not all([date_str, time_str, description]):
                messagebox.showerror("错误", "所有字段必须填写")
                return

            if not self.validate_date(date_str):
                messagebox.showerror("错误", "无效日期格式")
                return

            if not self.validate_time(time_str):
                messagebox.showerror("错误", "无效时间格式")
                return

            # 检查时间冲突
            event_list = self.events.get(date_str, [])
            if any(event["time"] == time_str for event in event_list):
                messagebox.showerror("错误", "该时间已有安排")
                return

            # 添加事件
            event_list.append({
                "time": time_str,
                "description": description
            })
            event_list.sort(key=lambda x: x["time"])
            self.events[date_str] = event_list
            self.save_events()
            self.update_calendar()
            dialog.destroy()

        # 确认按钮
        ttk.Button(dialog, text="确认添加", 
                command=on_confirm).grid(row=3, columnspan=2, pady=10)

        # 居中对话框
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"+{x}+{y}")

        # 绑定回车键
        dialog.bind("<Return>", lambda e: on_confirm())
    
    def delete_event(self):
        """删除选中事件（修复版）"""
        if not self.selected_date:
            messagebox.showwarning("提示", "请先选择日期")
            return
        
        selection = self.event_list.curselection()
        if not selection:
            return
        
        try:
            # 直接使用已存储的正确日期格式
            date_str = self.selected_date
            
            if messagebox.askyesno("确认", "确定要删除该事件吗？"):
                # 删除指定索引的事件
                del self.events[date_str][selection[0]]
                
                # 如果当天没有事件了，删除日期键
                if not self.events[date_str]:
                    del self.events[date_str]
                
                self.save_events()
                # 刷新事件列表显示
                self.show_events(int(date_str.split('-')[2]))
        except KeyError as e:
            messagebox.showerror("错误", f"事件删除失败: {str(e)}")
        except IndexError:
            messagebox.showerror("错误", "无效的事件索引")
    
    def prev_month(self):
        """切换至上个月"""
        self.current_date = self.current_date.replace(day=1)
        self.current_date = self.current_date.replace(month=self.current_date.month-1)
        self.update_calendar()
    
    def next_month(self):
        """切换至下个月"""
        self.current_date = self.current_date.replace(day=1)
        self.current_date = self.current_date.replace(month=self.current_date.month+1)
        self.update_calendar()
    
    @staticmethod
    def validate_date(date_str):
        """验证日期格式"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_time(time_str):
        """验证时间格式"""
        try:
            datetime.strptime(time_str, "%H:%M:%S")
            return True
        except ValueError:
            return False
    
    def load_events(self):
        """加载事件数据"""
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def save_events(self):
        """保存事件数据"""
        with open(DATA_FILE, 'w') as f:
            json.dump(self.events, f, indent=2)
        
    def init_agent(self):
        self.llm = ChatOpenAI(
            model="deepseek-chat",  # 根据DeepSeek实际模型名称调整
            openai_api_base="https://api.deepseek.com/v1",  # DeepSeek的API地址
            openai_api_key="sk-d07a8f9ffccb436fbc39f64317859243",
            temperature=0.3,  # 降低随机性
            max_tokens=500,   # 限制输出长度
            top_p=0.9
        ) 
        self.tools = [ add_schedule ]
        # self.tools = []
        # self.tools.append(
        #     Tool(
        #         name="partial_tool",
        #         func=functools.partial(self.add_schedule),
        #         description="Alternative approach"
        #     )
        # )

        self.llm_with_tools = self.llm.bind_tools(self.tools)

        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个日程管理助手",
                ),
                ("placeholder", "{chat_history}"),
                ("user", "{input} \n\n 当前时间为：{current_time}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )
        self.agent = create_tool_calling_agent(self.llm_with_tools, self.tools, self.prompt)
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=False)
if __name__ == "__main__":
    root = tk.Tk()
    global app 
    app = CalendarApp(root)
    root.mainloop()