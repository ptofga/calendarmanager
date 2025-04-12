import tkinter as tk
from tkinter import scrolledtext
import sqlite3
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
#import datetime
from langchain.callbacks.tracers import ConsoleCallbackHandler
from wxauto import *
from datetime import datetime

# 建表
# 连接到 SQLite 数据库
# 如果文件不存在，会自动在当前目录创建一个名为 'langchain.db' 的数据库文件
conn = sqlite3.connect('langchain.db')

# 创建一个 Cursor 对象并通过它执行 SQL 语句
c = conn.cursor()
# 创建表
c.execute('''
create table if not exists schedules 
(
    id          INTEGER
        primary key autoincrement,
    start_time  TEXT default (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')) not null,
    description TEXT default ''                                                  not null
);
''')


# 提交事务
conn.commit()
# 关闭连接
conn.close()

print("数据库和表已成功创建！")

def connect_db():
    """ 连接到数据库 """
    conn = sqlite3.connect('langchain.db')
    return conn
    
@tool
def add_schedule(start_time : str, description : str) -> str: 
    """ 新增日程，比如2024-05-03 20:00:00, 周会 """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO schedules (start_time, description) VALUES (?, ?);
    """, (start_time, description,))
    conn.commit()
    conn.close()
    return "true"

@tool
def delete_schedule_by_time(start_time : str) -> str:
    """ 根据时间删除日程 """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM schedules WHERE start_time = ?;
    """, (start_time,))
    conn.commit()
    conn.close()
    return "true"

@tool
def get_schedules_by_date(query_date : str) -> str:
    """ 根据日期查询日程，比如 获取2024-05-03的所有日程 """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT start_time, description FROM schedules WHERE start_time LIKE ?;
    """, (f"{query_date}%",))
    schedules = cursor.fetchall()
    conn.close()
    return str(schedules)

llm = ChatOpenAI(
    model="deepseek-chat",  # 根据DeepSeek实际模型名称调整
    openai_api_base="https://api.deepseek.com/v1",  # DeepSeek的API地址
    openai_api_key="xxxxxxxxxxxxxxxx",
    temperature=0.3,  # 降低随机性
    max_tokens=500,   # 限制输出长度
    top_p=0.9
) 
tools = [add_schedule, delete_schedule_by_time, get_schedules_by_date]
llm_with_tools = llm.bind_tools(tools)

prompt = ChatPromptTemplate.from_messages(
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
agent = create_tool_calling_agent(llm_with_tools, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

class QAApp:
    def __init__(self, master):
        self.master = master
        master.title("智能问答系统 v1.0")
        master.geometry("800x600")
        
        # 设置主题颜色
        self.bg_color = "#F0F0F0"
        self.btn_color = "#4CAF50"
        
        # 创建界面组件
        self.create_widgets()
 
        # 模拟问答函数（实际可替换为真实AI接口）
        self.qa_engine = self.mock_qa_engine


    def create_widgets(self):
        # 输入区域
        input_frame = tk.Frame(self.master, bg=self.bg_color)
        input_frame.pack(pady=20, padx=20, fill=tk.X)
        
        tk.Label(input_frame, 
                text="请输入您的问题：", 
                font=("微软雅黑", 12),
                bg=self.bg_color).pack(anchor=tk.W)
        
        self.input_txt = scrolledtext.ScrolledText(input_frame,
                                                 height=5,
                                                 font=("宋体", 12),
                                                 wrap=tk.WORD)
        self.input_txt.pack(fill=tk.X)
        self.input_txt.bind("<Return>", self.process_input)  # 绑定回车键
        
        # 按钮区域
        btn_frame = tk.Frame(self.master, bg=self.bg_color)
        btn_frame.pack(pady=10)
        
        self.getwx_btn = tk.Button(btn_frame,
                                  text="获取微信信息",
                                  command=self.get_wx_msg,
                                  bg=self.btn_color,
                                  fg="white",
                                  font=("微软雅黑", 12),
                                  width=15)
        self.getwx_btn.pack(side=tk.LEFT, padx=10)

        self.submit_btn = tk.Button(btn_frame,
                                  text="提交问题",
                                  command=self.process_input,
                                  bg=self.btn_color,
                                  fg="white",
                                  font=("微软雅黑", 12),
                                  width=15)
        self.submit_btn.pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame,
                text="清空内容",
                command=self.clear_all,
                bg="#607D8B",
                fg="white",
                font=("微软雅黑", 12),
                width=15).pack(side=tk.LEFT)

        # 输出区域
        output_frame = tk.Frame(self.master, bg=self.bg_color)
        output_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(output_frame, 
                text="系统回答：", 
                font=("微软雅黑", 12),
                bg=self.bg_color).pack(anchor=tk.W)
        
        self.output_txt = scrolledtext.ScrolledText(output_frame,
                                                  height=15,
                                                  font=("宋体", 12),
                                                  wrap=tk.WORD,
                                                  state=tk.DISABLED)
        self.output_txt.pack(fill=tk.BOTH, expand=True)


    def get_wx_msg(self):
        def is_valid_time(time_str: str) -> bool:
            """
            尝试通过 datetime 解析时间（允许灵活格式需调整）
            """
            try:
                datetime.strptime(time_str, "%H:%M")
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
                        self.input_txt.insert(tk.END,msg[1]) 
                else:
                    switch = is_valid_time(msg[1])
            return msg_list
        msgs_list=[]
        wx = WeChat()
        name_list = wx.GetAllSessionList()
        for name in name_list:
            msgs_list.append(get_more_messages(wx, name))
        


    def process_input(self, event=None):
        # 获取输入文本
        question = self.input_txt.get("1.0", tk.END).strip()
        
        if not question:
            self.show_output("提示：请输入有效问题！")
            return
        
        # 调用问答引擎
        answer = self.qa_engine(question)
        
        # 显示结果
        self.show_output(f"问题：{question}\n答案：{answer}\n{'-'*40}\n")
        self.input_txt.delete("1.0", tk.END)  # 清空输入框

    def show_output(self, text):
        self.output_txt.config(state=tk.NORMAL)
        self.output_txt.insert(tk.END, text + "\n")
        self.output_txt.see(tk.END)  # 自动滚动到底部
        self.output_txt.config(state=tk.DISABLED)

    def clear_all(self):
        self.input_txt.delete("1.0", tk.END)
        self.output_txt.config(state=tk.NORMAL)
        self.output_txt.delete("1.0", tk.END)
        self.output_txt.config(state=tk.DISABLED)

    def mock_qa_engine(self, question):
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        res = agent_executor.invoke(
                {
                    "input": question,
                    "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                #config={"callbacks": [ConsoleCallbackHandler()]}
            )
        
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return res["output"]

if __name__ == "__main__":
    root = tk.Tk()
    app = QAApp(root)
    root.mainloop()