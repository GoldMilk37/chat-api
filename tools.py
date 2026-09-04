# tools.py
import json
import ast
import operator
from typing import Dict, Any

# ============ 工具函数定义 ============

def calculator(expression: str) -> float:
    """执行四则运算（安全版本）"""
    try:
        # 使用 ast 模块安全地计算数学表达式
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        
        def eval_expr(node):
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.BinOp):
                return operators[type(node.op)](
                    eval_expr(node.left),
                    eval_expr(node.right)
                )
            elif isinstance(node, ast.UnaryOp):
                return operators[type(node.op)](eval_expr(node.operand))
            elif isinstance(node, ast.Expression):
                return eval_expr(node.body)
            else:
                raise TypeError(f"不支持的表达式类型: {type(node)}")
        
        tree = ast.parse(expression, mode='eval')
        result = eval_expr(tree)
        return float(result)
    except Exception as e:
        return f"计算错误: {str(e)}"


def get_weather(city: str, date: str = "今天") -> str:
    """模拟天气查询"""
    weather_database = {
        "北京": {
            "今天": "晴天，25°C，空气质量良好",
            "明天": "多云，22°C，微风",
            "后天": "小雨，18°C，记得带伞"
        },
        "上海": {
            "今天": "小雨，20°C，湿度较大",
            "明天": "阴天，23°C，适合出行",
            "后天": "晴，26°C，注意防晒"
        },
        "广州": {
            "今天": "多云，28°C，闷热",
            "明天": "雷阵雨，27°C，带伞",
            "后天": "晴，30°C，高温"
        },
        "深圳": {
            "今天": "晴，27°C，适合户外活动",
            "明天": "多云，26°C，舒适",
            "后天": "小雨，24°C，降温"
        }
    }
    
    weather_info = weather_database.get(city, {}).get(date, f"暂无{city}{date}的天气数据")
    return f"{city}{date}天气：{weather_info}"


# ============ 工具 Schema 定义 ============

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "执行四则运算，支持加减乘除和括号。当用户需要进行数学计算时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，例如：'2+3*4'、'(10-5)*3'、'23*17'等"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的天气情况。当用户询问天气相关信息时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如：北京、上海、广州、深圳等"
                    },
                    "date": {
                        "type": "string",
                        "description": "日期，可以是'今天'、'明天'、'后天'等",
                        "default": "今天"
                    }
                },
                "required": ["city"]
            }
        }
    }
]


# ============ 工具执行器 ============

class ToolExecutor:
    def __init__(self):
        self.function_map = {
            "calculator": calculator,
            "get_weather": get_weather
        }
    
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str: # 表示 arguments 是一个字典，其中：键（key）：必须是字符串类型（str）值（value）：可以是任意类型（Any）
        """执行工具函数"""
        if tool_name not in self.function_map:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
        
        try:
            func = self.function_map[tool_name] # 从映射表中获取对应的函数对象 赋值给变量 func
            result = func(**arguments) # **arguments：将参数字典解包为关键字参数执行结果赋值给 result
            return json.dumps({"result": result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"执行错误: {str(e)}"}, ensure_ascii=False)