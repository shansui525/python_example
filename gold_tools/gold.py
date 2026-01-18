import tkinter as tk
from tkinter import ttk, messagebox  # 导入 messagebox 模块
import pandas as pd
import json
import uuid  # 导入 uuid 模块
from gold_sina import getPrice

class PandaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("实时计算GUI")

        # self.root.geometry("800x400")

        # 设置主窗口的行和列的权重，使其可以自适应缩放
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # 创建 PanedWindow
        self.paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned_window.grid(row=0, column=0, sticky="nsew")

        # 创建数据录入框架
        self.create_input_frame()

        # 创建数据明细框架
        self.create_table_frame()

        # 存储数据的DataFrame
        self.data = pd.DataFrame(columns=["uuid", "买入日期", "标的", "买入价格", "规格", "卖出日期", "卖出价格", "损益"])

        # 加载已保存的数据
        self.load_data()

        # 初始化实时显示框
        self.update_summary()

        # 初始化实时金价和价值显示
        self.update_real_time()
        self.schedule_update()

    def export_data(self):
        # 将数据导出为格式化的JSON文件
        with open("exported_data.json", "w", encoding="utf-8") as f:
            self.data.to_json(f, orient="records", force_ascii=False, indent=4)
        messagebox.showinfo("导出成功", "数据已成功导出到 exported_data.json")

    def create_input_frame(self):
        # 创建数据录入框架
        self.input_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.input_frame)

        # 设置数据录入框架的行和列的权重
        self.input_frame.grid_rowconfigure(0, weight=1)
        self.input_frame.grid_rowconfigure(1, weight=1)
        self.input_frame.grid_rowconfigure(2, weight=1)
        self.input_frame.grid_rowconfigure(3, weight=1)
        self.input_frame.grid_rowconfigure(4, weight=1)
        self.input_frame.grid_rowconfigure(5, weight=1)
        self.input_frame.grid_rowconfigure(6, weight=1)
        self.input_frame.grid_columnconfigure(0, weight=1)
        self.input_frame.grid_columnconfigure(1, weight=1)

        # 买入日期
        self.buy_date_label = tk.Label(self.input_frame, text="买入日期:")
        self.buy_date_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.buy_date_entry = tk.Entry(self.input_frame)
        self.buy_date_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        # 标的
        self.symbol_label = tk.Label(self.input_frame, text="标的:")
        self.symbol_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.symbol_entry = tk.Entry(self.input_frame)
        self.symbol_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # 规格
        self.spec_label = tk.Label(self.input_frame, text="规格:")
        self.spec_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.spec_options = ["1g","3g","8g","15g", "20g", "30g", "50g","57g","1/20oz","1/10oz","1/4oz","1/2oz","1oz","59.1g"]
        self.spec_var = tk.StringVar()
        self.spec_combobox = ttk.Combobox(self.input_frame, textvariable=self.spec_var, values=self.spec_options)
        self.spec_combobox.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # 买入价格
        self.buy_price_label = tk.Label(self.input_frame, text="买入价格:")
        self.buy_price_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.buy_price_entry = tk.Entry(self.input_frame)
        self.buy_price_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        # 卖出日期
        self.sell_date_label = tk.Label(self.input_frame, text="卖出日期:")
        self.sell_date_label.grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.sell_date_entry = tk.Entry(self.input_frame)
        self.sell_date_entry.grid(row=4, column=1, padx=10, pady=5, sticky="ew")

        # 卖出价格
        self.sell_price_label = tk.Label(self.input_frame, text="卖出价格:")
        self.sell_price_label.grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.sell_price_entry = tk.Entry(self.input_frame)
        self.sell_price_entry.grid(row=5, column=1, padx=10, pady=5, sticky="ew")

        # 创建按钮
        self.submit_button = tk.Button(self.input_frame, text="确认", command=self.add_or_modify_data)
        self.submit_button.grid(row=6, column=0, padx=10, pady=10, sticky="ew")

        self.cancel_button = tk.Button(self.input_frame, text="取消", command=self.cancel_selection)
        self.cancel_button.grid(row=6, column=1, padx=10, pady=10, sticky="ew")

    def create_table_frame(self):
        # 创建数据明细框架
        self.table_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.table_frame)

        # 设置数据明细框架的行和列的权重
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_rowconfigure(1, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)

        # 创建表格
        self.tree = ttk.Treeview(self.table_frame, columns=("uuid", "买入日期", "标的", "买入价格", "规格", "卖出日期", "卖出价格", "损益"), show="headings")
        self.tree.heading("uuid", text="UUID")
        self.tree.heading("买入日期", text="买入日期")
        self.tree.heading("标的", text="标的")
        self.tree.heading("买入价格", text="买入价格")
        self.tree.heading("规格", text="规格")
        self.tree.heading("卖出日期", text="卖出日期")
        self.tree.heading("卖出价格", text="卖出价格")
        self.tree.heading("损益", text="损益")

        # 创建垂直滚动条
        yscroll = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscroll.set)

        # 创建水平滚动条
        xscroll = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=xscroll.set)

        self.tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # 绑定选中事件
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # 创建实时显示框
        self.summary_label = tk.Label(self.table_frame, text="总克重: 0.0g | 买入总价: 0.0元 | 买入平均价格: 0.0元/g")
        self.summary_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        # 创建实时金价和价值显示框
        self.real_time_label = tk.Label(self.table_frame, text="当前金价: 0.0元/g | 现有黄金价值: 0.0元")
        self.real_time_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")

        # 创建导出按钮
        self.export_button = tk.Button(self.table_frame, text="导出数据", command=self.export_data)
        self.export_button.grid(row=2, column=1, padx=10, pady=5, sticky="e")

    def add_or_modify_data(self):
        buy_date = self.buy_date_entry.get()
        symbol = self.symbol_entry.get()
        buy_price = self.buy_price_entry.get()
        spec = self.spec_var.get()
        sell_date = self.sell_date_entry.get()
        sell_price = self.sell_price_entry.get()

        # 校验必填字段
        if not buy_date or not symbol or not buy_price or not spec:
            messagebox.showerror("输入错误", "买入日期、标的、买入价格、规格为必填项")
            return

        buy_price = float(buy_price)
        if sell_price:
            sell_price = float(sell_price)
            profit_loss = sell_price - buy_price
        else:
            sell_price = 0
            profit_loss = 0

        # 检查是否选中了表格中的数据
        selected_item = self.tree.selection()
        if selected_item:
            # 修改数据
            item_values = self.tree.item(selected_item[0], "values")
            item_id = selected_item[0]
            s_uuid = item_values[0]

            # 查找匹配的记录
            matching_indices = self.data.index[self.data["uuid"] == s_uuid]

            if not matching_indices.empty:
                index = matching_indices[0]
                self.data.at[index, "买入日期"] = buy_date
                self.data.at[index, "标的"] = symbol
                self.data.at[index, "买入价格"] = buy_price
                self.data.at[index, "规格"] = spec
                self.data.at[index, "卖出日期"] = sell_date
                self.data.at[index, "卖出价格"] = sell_price
                self.data.at[index, "损益"] = profit_loss

                # 更新表格
                self.tree.item(item_id, values=(s_uuid, buy_date, symbol, buy_price, spec, sell_date, sell_price, profit_loss))
            else:
                messagebox.showerror("修改错误", "未找到匹配的记录")
        else:
            # 新增数据
            new_uuid = str(uuid.uuid4())
            new_data = pd.DataFrame(
                {"uuid": [new_uuid], "买入日期": [buy_date], "标的": [symbol], "买入价格": [buy_price], "规格": [spec], "卖出日期": [sell_date], "卖出价格": [sell_price],
                 "损益": [profit_loss]})
            self.data = pd.concat([self.data, new_data], ignore_index=True)

            # 更新表格
            self.tree.insert("", "end", values=(new_uuid, buy_date, symbol, buy_price, spec, sell_date, sell_price, profit_loss))

        # 保存数据
        self.save_data()

        # 清空输入框
        self.buy_date_entry.delete(0, tk.END)
        self.symbol_entry.delete(0, tk.END)
        self.buy_price_entry.delete(0, tk.END)
        self.spec_combobox.set("")
        self.sell_date_entry.delete(0, tk.END)
        self.sell_price_entry.delete(0, tk.END)

        # 更新实时显示框
        self.update_summary()

        # 更新实时金价和价值
        self.update_real_time()

    def on_tree_select(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            item_values = self.tree.item(selected_item[0], "values")
            self.buy_date_entry.delete(0, tk.END)
            self.buy_date_entry.insert(0, item_values[1])
            self.symbol_entry.delete(0, tk.END)
            self.symbol_entry.insert(0, item_values[2])
            self.buy_price_entry.delete(0, tk.END)
            self.buy_price_entry.insert(0, item_values[3])
            self.spec_combobox.set(item_values[4])
            self.sell_date_entry.delete(0, tk.END)
            self.sell_date_entry.insert(0, item_values[5])
            self.sell_price_entry.delete(0, tk.END)
            self.sell_price_entry.insert(0, item_values[6])

    def save_data(self):
        with open("data.json", "w") as f:
            self.data.to_json(f, orient="records", force_ascii=False)

    def load_data(self):
        try:
            with open("data.json", "r") as f:
                data = pd.read_json(f, orient="records")
                self.data = data
                for index, row in data.iterrows():
                    self.tree.insert("", "end", values=(row["uuid"], row["买入日期"], row["标的"], row["买入价格"], row["规格"], row["卖出日期"], row["卖出价格"], row["损益"]))
        except FileNotFoundError:
            pass

    def cancel_selection(self):
        # 取消选中
        self.tree.selection_remove(self.tree.selection())
        # 清空输入框
        self.buy_date_entry.delete(0, tk.END)
        self.symbol_entry.delete(0, tk.END)
        self.buy_price_entry.delete(0, tk.END)
        self.spec_combobox.set("")
        self.sell_date_entry.delete(0, tk.END)
        self.sell_price_entry.delete(0, tk.END)

    def update_summary(self):
        # 计算总克重
        self.total_weight = 0.0
        self.total_buy_price = 0.0
        self.total_profit = 0.0

        for index, row in self.data.iterrows():
            if pd.isna(row["卖出日期"]) or row["卖出日期"] == "":
                spec = row["规格"]
                if spec == "1g":
                    self.total_weight += 1
                elif spec == "3g":
                    self.total_weight += 3
                elif spec == "8g":
                    self.total_weight += 8
                elif spec == "15g":
                    self.total_weight += 15
                elif spec == "20g":
                    self.total_weight += 20
                elif spec == "30g":
                    self.total_weight += 30
                elif spec == "50g":
                    self.total_weight += 50
                elif spec == "57g":
                    self.total_weight += 57
                elif spec == "1/20oz":
                    self.total_weight += 1.55
                elif spec == "1/10oz":
                    self.total_weight += 3.11
                elif spec == "1/4oz":
                    self.total_weight += 7.77
                elif spec == "1/2oz":
                    self.total_weight += 15.5
                elif spec == "1oz":
                    self.total_weight += 31.1
                elif spec == "59.1g":
                    self.total_weight += 59.1

                self.total_buy_price += float(row["买入价格"])
            self.total_profit += float(row["损益"])

        # 计算买入平均价格
        if self.total_weight > 0:
            self.avg_buy_price = self.total_buy_price / self.total_weight
            self.avg_buy_except_profit_price = (self.total_buy_price - self.total_profit) / self.total_weight
        else:
            self.avg_buy_price = 0.0
            self.avg_buy_except_profit_price = 0.0

        # 更新显示框
        summary_text = f"总克重: {self.total_weight:.2f}g | 买入总价: {self.total_buy_price:.2f}元 | 买入平均价格: {self.avg_buy_price:.2f}元/g | 去损益后平均价格：{self.avg_buy_except_profit_price:.2f}元/g | 损益：{self.total_profit:.2f} 元"
        self.summary_label.config(text=summary_text)

    def update_real_time(self):
        # 获取实时金价
        try:
            self.current_price = getPrice('gds_AUTD')  # 假设 getPrice() 返回元/克的浮点数
        except Exception as e:
            self.current_price = 0.0  # 如果 API 调用失败，使用默认值

        # 计算现有黄金价值
        current_value = self.total_weight * self.current_price

        # 更新显示框
        real_time_text = f"当前金价: {self.current_price:.2f}元/g | 现有黄金价值: {current_value:.2f}元"
        self.real_time_label.config(text=real_time_text)

    def schedule_update(self):
        self.update_real_time()
        self.root.after(10000, self.schedule_update)  # 每10秒更新一次

if __name__ == "__main__":
    root = tk.Tk()
    app = PandaGUI(root)
    root.mainloop()