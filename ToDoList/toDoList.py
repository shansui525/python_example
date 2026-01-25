import tkinter as tk
from tkinter import messagebox, ttk, simpledialog  # GUI 组件库
import json  # 数据序列化
import os  # 文件系统操作
import hashlib  # 哈希算法
import base64  # 编码/解码
from cryptography.fernet import Fernet, InvalidToken  # 加密/解密库

# 注意：运行前需 pip install cryptography

# 文件名
DATA_FILE = "todo.enc"  # 改成 .enc 表示加密文件 - 存储加密后的待办事项数据

tasks = []  # 存储 [任务文字, 是否完成] - 全局变量，存储所有待办事项

# 派生密钥函数（使用 PBKDF2 简单实现）
def derive_key(password: str) -> bytes:
    """
    从用户密码派生加密密钥

    @param password: 用户输入的密码
    @return: Fernet 加密所需的密钥
    """
    salt = b'simple_todo_salt'  # 固定盐（生产环境应随机生成并存储）
    kdf = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=32)
    return base64.urlsafe_b64encode(kdf)

# 加载任务（解密）
def load_tasks(password: str) -> bool:
    """
    从加密文件加载任务数据

    @param password: 用于解密文件的密码
    @return: 加载成功返回 True，否则返回 False
    """
    global tasks
    if os.path.exists(DATA_FILE):
        key = derive_key(password)
        fernet = Fernet(key)
        try:
            with open(DATA_FILE, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = fernet.decrypt(encrypted_data)
            tasks = json.loads(decrypted_data.decode('utf-8'))
            # 校验格式
            if not isinstance(tasks, list) or not all(isinstance(t, list) and len(t) == 2 for t in tasks):
                tasks = []
                messagebox.showwarning("提示", "数据格式异常，已清空")
            return True
        except (InvalidToken, json.JSONDecodeError):
            messagebox.showerror("错误", "密码错误或文件损坏！")
            return False
    else:
        # 文件不存在，视为第一次使用
        tasks = []
        return True

# 保存任务（加密）
def save_tasks(password: str):
    """
    将任务数据加密并保存到文件

    @param password: 用于加密文件的密码
    """
    key = derive_key(password)
    fernet = Fernet(key)
    try:
        data = json.dumps(tasks, ensure_ascii=False, indent=2).encode('utf-8')
        encrypted_data = fernet.encrypt(data)
        with open(DATA_FILE, 'wb') as f:
            f.write(encrypted_data)
    except Exception as e:
        messagebox.showerror("保存失败", f"无法保存任务：{e}")

def add_task():
    """
    添加新的待办事项
    """
    text = entry.get().strip()  # 获取输入框中的文本并去除首尾空白
    if text:  # 如果文本不为空
        tasks.append([text, False])  # 添加新任务到列表，初始状态为未完成
        update_listbox()  # 更新列表显示
        entry.delete(0, tk.END)  # 清空输入框
        save_tasks(current_password)  # 使用当前密码保存到文件
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
        save_tasks(current_password)  # 保存到文件
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
        save_tasks(current_password)  # 保存到文件
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

# 启动时处理密码
if os.path.exists(DATA_FILE):
    password_prompt = "请输入密码解锁任务列表"  # 文件存在，要求输入密码
else:
    password_prompt = "第一次使用，请设置密码（用于加密文件）"  # 文件不存在，首次使用

success = False
while not success:
    # 弹出密码输入对话框
    current_password = simpledialog.askstring("密码验证", password_prompt, show='*')
    if current_password is None:  # 用户取消
        root.destroy()
        exit()
    success = load_tasks(current_password)  # 尝试加载数据
    if not success:
        password_prompt = "密码错误，请重试"  # 密码错误，重新提示

# 输入区域
frame_input = tk.Frame(root)  # 创建输入区域框架
frame_input.pack(pady=12, padx=20, fill=tk.X)  # 布局框架

entry = tk.Entry(frame_input, font=("Consolas", 14), width=28)  # 创建输入框
entry.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)  # 布局输入框

btn_add = tk.Button(frame_input, text="新增", width=10, command=add_task)  # 创建添加按钮
btn_add.pack(side=tk.LEFT)  # 布局添加按钮

# 工具栏
frame_tools = tk.Frame(root)  # 创建工具栏框架
frame_tools.pack(pady=8, padx=20, fill=tk.X)  # 布局工具栏框架

topmost_var = tk.BooleanVar(value=False)  # 创建布尔变量用于存储置顶状态
chk_topmost = ttk.Checkbutton(frame_tools, text="窗口置顶", variable=topmost_var, command=toggle_topmost)  # 创建置顶复选框
chk_topmost.pack(side=tk.LEFT)  # 布局置顶复选框

btn_delete = tk.Button(frame_tools, text="删除选中", width=12, command=delete_task)  # 创建删除按钮
btn_delete.pack(side=tk.RIGHT)  # 布局删除按钮

# 任务列表
listbox = tk.Listbox(root, font=("Consolas", 13), height=20, width=48, selectbackground="#a6d6ff", selectmode=tk.SINGLE)  # 创建列表框
listbox.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)  # 布局列表框

listbox.bind("<Double-Button-1>", toggle_complete)  # 绑定双击事件到切换完成状态功能

# 回车添加
root.bind('<Return>', lambda e: add_task())  # 绑定回车键到添加任务功能

# 关闭时保存
root.protocol("WM_DELETE_WINDOW", lambda: (save_tasks(current_password), root.destroy()))  # 绑定窗口关闭事件，先保存数据再关闭

# 初始刷新 & 焦点
update_listbox()  # 初始更新列表显示
entry.focus()  # 设置输入框获得焦点

root.mainloop()  # 启动GUI主循环
