import tkinter as tk
from tkinter import messagebox, ttk
import json
import os

# 文件名
DATA_FILE = "todo.json"  # 定义存储待办事项数据的文件名

tasks = []  # 存储 [任务文字, 是否完成] - 全局变量，存储所有待办事项

def load_tasks():
    """
    从文件加载待办事项数据
    """
    global tasks
    if os.path.exists(DATA_FILE):  # 检查数据文件是否存在
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:  # 以UTF-8编码打开文件
                tasks = json.load(f)  # 从JSON文件加载数据到tasks列表
            # 验证数据格式是否正确
            if not isinstance(tasks, list) or not all(isinstance(t, list) and len(t) == 2 for t in tasks):
                tasks = []  # 如果格式不正确，清空tasks
        except:
            tasks = []  # 加载失败时清空tasks

def save_tasks():
    """
    将待办事项数据保存到文件
    """
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:  # 以UTF-8编码写入文件
            json.dump(tasks, f, ensure_ascii=False, indent=2)  # 将tasks保存为格式化的JSON
    except:
        pass  # 静默失败，避免打扰用户

def add_task():
    """
    添加新的待办事项
    """
    text = entry.get().strip()  # 获取输入框中的文本并去除首尾空白
    if text:  # 如果文本不为空
        tasks.append([text, False])  # 添加新任务到列表，初始状态为未完成
        update_listbox()  # 更新列表显示
        entry.delete(0, tk.END)  # 清空输入框
        save_tasks()  # 保存到文件
    else:
        messagebox.showwarning("提示", "请输入内容～")  # 输入为空时显示警告

def toggle_complete(event):
    """
    切换任务的完成状态
    @param event: 双击事件对象
    """
    try:
        index = listbox.curselection()[0]  # 获取当前选中的任务索引
        tasks[index][1] = not tasks[index][1]  # 切换完成状态
        update_listbox()  # 更新列表显示
        save_tasks()  # 保存到文件
    except:
        pass  # 未选中项目时静默处理

def delete_task():
    """
    删除选中的待办事项
    """
    try:
        index = listbox.curselection()[0]  # 获取当前选中的任务索引
        tasks.pop(index)  # 从列表中移除该任务
        update_listbox()  # 更新列表显示
        save_tasks()  # 保存到文件
    except:
        messagebox.showwarning("提示", "请先选择一项")  # 未选中项目时显示警告

def update_listbox():
    """
    更新列表框显示
    """
    listbox.delete(0, tk.END)  # 清空列表框
    for text, done in tasks:  # 遍历所有任务
        prefix = "✓ " if done else "□ "  # 根据完成状态添加前缀标记
        listbox.insert(tk.END, prefix + text)  # 在列表框中插入任务
        if done:  # 如果任务已完成
            # 设置已完成任务的样式（灰色文字，浅色背景）
            listbox.itemconfig(tk.END, {'fg': 'gray', 'selectbackground': '#d0d0d0'})

def toggle_topmost():
    """
    切换窗口置顶状态
    """
    root.attributes('-topmost', topmost_var.get())  # 根据复选框状态设置窗口置顶属性

# ── 主窗口 ──
root = tk.Tk()  # 创建主窗口
root.title("我的待办")  # 设置窗口标题
root.geometry("480x560")  # 设置窗口大小

# 先加载数据
load_tasks()

# 顶部输入区域
frame_input = tk.Frame(root)  # 创建输入区域框架
frame_input.pack(pady=12, padx=20, fill=tk.X)  # 布局框架

entry = tk.Entry(frame_input, font=("Consolas", 14), width=28)  # 创建输入框
entry.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)  # 布局输入框

btn_add = tk.Button(frame_input, text="新增", width=10, command=add_task)  # 创建添加按钮
btn_add.pack(side=tk.LEFT)  # 布局添加按钮

# 置顶开关 + 删除按钮 放在同一行
frame_tools = tk.Frame(root)  # 创建工具栏框架
frame_tools.pack(pady=8, padx=20, fill=tk.X)  # 布局工具栏框架

topmost_var = tk.BooleanVar(value=False)  # 默认不置顶 - 创建布尔变量用于存储置顶状态
# 创建现代化的置顶复选框
chk_topmost = ttk.Checkbutton(
    frame_tools,  # 父容器
    text="窗口置顶",  # 显示文本
    variable=topmost_var,  # 绑定变量
    command=toggle_topmost,  # 点击时执行的函数
    style="Switch.TCheckbutton"   # 现代风格（部分系统支持）- 设置为开关样式
)
chk_topmost.pack(side=tk.LEFT)  # 布局置顶复选框

btn_delete = tk.Button(frame_tools, text="删除选中", width=12, command=delete_task)  # 创建删除按钮
btn_delete.pack(side=tk.RIGHT)  # 布局删除按钮

# 任务列表
listbox = tk.Listbox(  # 创建列表框
    root,
    font=("Consolas", 13),  # 字体设置
    height=20,  # 列表高度
    width=48,  # 列表宽度
    selectbackground="#a6d6ff",  # 选中项背景色
    selectmode=tk.SINGLE  # 单选模式
)
listbox.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)  # 布局列表框

listbox.bind("<Double-Button-1>", toggle_complete)  # 绑定双击事件到切换完成状态功能

# 回车添加
root.bind('<Return>', lambda e: add_task())  # 绑定回车键到添加任务功能

# 窗口关闭时保存
root.protocol("WM_DELETE_WINDOW", lambda: (save_tasks(), root.destroy()))  # 绑定窗口关闭事件，先保存数据再关闭

# 初始刷新 & 焦点
update_listbox()  # 初始更新列表显示
entry.focus()  # 设置输入框获得焦点

root.mainloop()  # 启动GUI主循环
