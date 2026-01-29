import logging
import sys
from datetime import datetime

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_logger(name: str) -> logging.Logger:
    """获取 logger 实例"""
    return logging.getLogger(name)

# 兼容性别名
setup_logger = get_logger

# 预定义的 loggers
workflow_logger = get_logger("workflow")
structure_logger = get_logger("structure_agent")
style_logger = get_logger("style_agent")
planner_logger = get_logger("planner_agent")
worker_logger = get_logger("worker_agent")
test_runner_logger = get_logger("test_runner")
report_logger = get_logger("report_agent")
