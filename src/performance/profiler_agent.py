"""
Profiler Agent - 性能剖析器
负责运行实际的性能分析工具收集 CPU/内存数据
"""
import os
import subprocess
import re
import sys
import threading
import time
from typing import Dict, Any, Optional
from .perf_state import PerformanceState, ProfilingData
from ..utils.logger import setup_logger

logger = setup_logger("profiler_agent")


class ProfilerAgent:
    """性能剖析器 Agent"""
    
    def __init__(self):
        # 检测可用的 profiling 工具
        self.available_tools = self._detect_available_tools()
        logger.info(f"可用的 profiling 工具: {self.available_tools}")
    
    def _detect_available_tools(self) -> Dict[str, bool]:
        """检测系统上可用的 profiling 工具"""
        tools = {
            'perf': False,
            'gprof': False,
            'valgrind': False,
            'time': False,
        }
        
        for tool in tools:
            try:
                result = subprocess.run(
                    ['which', tool],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                tools[tool] = result.returncode == 0
            except Exception:
                pass
        
        # time 通常总是可用的
        tools['time'] = True
        
        return tools
    
    def profile(self, state: PerformanceState) -> Dict[str, Any]:
        """执行性能剖析"""
        project_path = state["project_path"]
        profiling_enabled = state.get("profiling_enabled", False)
        
        if not profiling_enabled:
            logger.info("性能剖析已禁用，跳过")
            return {"profiling_data": None, "profiling_output": ""}
        
        logger.info(f"开始性能剖析，项目: {project_path}")

        # 用户可选指定：可执行文件 / 运行参数 / 工作目录
        user_executable = state.get("profiling_executable")
        user_args = state.get("profiling_args") or []
        user_cwd = state.get("profiling_cwd")
        
        run_cwd = user_cwd or project_path

        # 若用户传入相对路径，则按 run_cwd（优先）或 project_path 解析
        resolved_user_executable = None
        if user_executable:
            resolved_user_executable = user_executable
            if not os.path.isabs(resolved_user_executable):
                resolved_user_executable = os.path.normpath(os.path.join(run_cwd, resolved_user_executable))

        # 检测项目类型和可执行文件
        executable = resolved_user_executable or self._find_executable(project_path)
        
        if not executable:
            logger.warning("未找到可执行文件，无法进行性能剖析")
            return {"profiling_data": None, "profiling_output": ""}

        if resolved_user_executable and not (
            os.path.exists(resolved_user_executable) and os.access(resolved_user_executable, os.X_OK)
        ):
            logger.warning(
                "指定的可执行文件不可用或不可执行: "
                f"{resolved_user_executable} (来自 --exec {user_executable}, cwd={run_cwd})"
            )
            return {"profiling_data": None, "profiling_output": ""}
        
        # 尝试使用可用的工具进行剖析
        profiling_data = None
        profiling_output = ""
        
        if self.available_tools.get('perf'):
            profiling_data, profiling_output = self._profile_with_perf(executable, run_cwd, user_args)
        elif self.available_tools.get('time'):
            profiling_data, profiling_output = self._profile_with_time(executable, run_cwd, user_args)
        
        if profiling_data:
            logger.info(f"性能剖析完成，总时间: {profiling_data.get('total_time', 'N/A')}")
        
        return {"profiling_data": profiling_data, "profiling_output": profiling_output}

    def _run_process_with_live_output(self, cmd: list[str], cwd: str, timeout_s: int = 60) -> tuple[int, str, str]:
        """运行命令，实时把 stdout/stderr 打到当前终端，同时捕获全文本。"""
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        logger.info(f"[profiling] 运行命令: {' '.join(cmd)}")
        logger.info(f"[profiling] 工作目录: {cwd}")

        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def _reader(stream, sink, buffer):
            try:
                for line in iter(stream.readline, ''):
                    sink.write(line)
                    sink.flush()
                    buffer.append(line)
            finally:
                try:
                    stream.close()
                except Exception:
                    pass

        t_out = threading.Thread(target=_reader, args=(proc.stdout, sys.stdout, stdout_lines), daemon=True)
        t_err = threading.Thread(target=_reader, args=(proc.stderr, sys.stderr, stderr_lines), daemon=True)
        t_out.start()
        t_err.start()

        start = time.time()
        while True:
            if proc.poll() is not None:
                break
            if time.time() - start > timeout_s:
                logger.warning(f"profiling 超时（>{timeout_s}s），终止进程")
                try:
                    proc.kill()
                except Exception:
                    pass
                break
            time.sleep(0.05)

        rc = proc.wait(timeout=5)
        t_out.join(timeout=1)
        t_err.join(timeout=1)
        return rc, ''.join(stdout_lines), ''.join(stderr_lines)
    
    def _find_executable(self, project_path: str) -> Optional[str]:
        """查找项目的可执行文件"""
        # 常见的可执行文件位置
        possible_paths = [
            os.path.join(project_path, "build", "project_hw"),
            os.path.join(project_path, "build", "main"),
            os.path.join(project_path, "a.out"),
            os.path.join(project_path, "main"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        
        # 搜索 build 目录
        build_dir = os.path.join(project_path, "build")
        if os.path.exists(build_dir):
            for f in os.listdir(build_dir):
                path = os.path.join(build_dir, f)
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    # 排除一些常见的非目标文件
                    if not f.endswith(('.cmake', '.txt', '.sh')):
                        return path
        
        return None
    
    def _profile_with_perf(self, executable: str, cwd: str, user_args: list[str]) -> tuple[Optional[ProfilingData], str]:
        """使用 perf 进行性能剖析"""
        logger.info(f"使用 perf 分析: {executable}")
        
        try:
            # 构建命令：如果用户提供了参数，则完全沿用；否则尝试自动填充常见输入输出
            cmd = [executable] + list(user_args)
            if not user_args:
                input_file = self._find_test_input(cwd)
                if input_file:
                    cmd.extend(["-i", input_file, "-o", "/tmp/perf_test_out.txt"])
            
            # 运行 perf stat
            perf_cmd = ["perf", "stat", "-e", 
                       "cycles,instructions,cache-misses,cache-references"] + cmd
            
            rc, out, err = self._run_process_with_live_output(perf_cmd, cwd=cwd, timeout_s=60)
            # perf stat 的统计输出通常在 stderr
            profiling_output = (out + "\n" + err).strip()
            if rc != 0:
                logger.warning(f"perf 返回非 0 退出码: {rc}")
            return self._parse_perf_output(err), profiling_output
            
        except subprocess.TimeoutExpired:
            logger.warning("perf 分析超时")
        except Exception as e:
            logger.warning(f"perf 分析失败: {e}")
        
        return None, ""
    
    def _profile_with_time(self, executable: str, cwd: str, user_args: list[str]) -> tuple[Optional[ProfilingData], str]:
        """使用 time 进行基本计时"""
        logger.info(f"使用 time 分析: {executable}")
        
        try:
            cmd = [executable] + list(user_args)
            if not user_args:
                input_file = self._find_test_input(cwd)
                if input_file:
                    cmd.extend(["-i", input_file, "-o", "/tmp/time_test_out.txt"])
            
            # 使用 time
            time_cmd = ["/usr/bin/time", "-v"] + cmd
            
            rc, out, err = self._run_process_with_live_output(time_cmd, cwd=cwd, timeout_s=60)
            profiling_output = (out + "\n" + err).strip()
            if rc != 0:
                logger.warning(f"time 返回非 0 退出码: {rc}")
            return self._parse_time_output(err), profiling_output
            
        except subprocess.TimeoutExpired:
            logger.warning("time 分析超时")
        except Exception as e:
            logger.warning(f"time 分析失败: {e}")
        
        return None, ""
    
    def _find_test_input(self, project_path: str) -> Optional[str]:
        """查找测试输入文件"""
        dataset_dir = os.path.join(project_path, "dataset")
        if os.path.exists(dataset_dir):
            for f in os.listdir(dataset_dir):
                if f.startswith("input") and f.endswith(".txt"):
                    return os.path.join(dataset_dir, f)
        return None
    
    def _parse_perf_output(self, output: str) -> ProfilingData:
        """解析 perf stat 输出"""
        hotspots = []
        cache_info = {}
        total_time = "N/A"
        
        # 解析时间
        time_match = re.search(r'(\d+\.\d+)\s+seconds time elapsed', output)
        if time_match:
            total_time = f"{time_match.group(1)}s"
        
        # 解析 cache 信息
        cache_miss_match = re.search(r'([\d,]+)\s+cache-misses.*#\s*([\d.]+)\s*%', output)
        if cache_miss_match:
            cache_info["miss_rate"] = f"{cache_miss_match.group(2)}%"
        
        # 解析指令数
        instructions_match = re.search(r'([\d,]+)\s+instructions', output)
        if instructions_match:
            cache_info["instructions"] = instructions_match.group(1)
        
        return ProfilingData(
            total_time=total_time,
            hotspots=hotspots,  # perf stat 不提供热点信息
            memory_peak="N/A",
            cache_info=cache_info
        )
    
    def _parse_time_output(self, output: str) -> ProfilingData:
        """解析 time -v 输出"""
        total_time = "N/A"
        memory_peak = "N/A"
        cache_info: Dict[str, Any] = {}
        
        # 解析 wall clock time
        time_match = re.search(r'Elapsed \(wall clock\) time.*: ([\d:\.]+)', output)
        if time_match:
            total_time = time_match.group(1)

        # 解析 user / system time
        user_match = re.search(r'User time \(seconds\):\s*([\d\.]+)', output)
        if user_match:
            cache_info["user_time_s"] = user_match.group(1)
        sys_match = re.search(r'System time \(seconds\):\s*([\d\.]+)', output)
        if sys_match:
            cache_info["system_time_s"] = sys_match.group(1)

        # 解析 CPU 使用率
        cpu_match = re.search(r'Percent of CPU this job got:\s*(\d+)%', output)
        if cpu_match:
            cache_info["cpu_percent"] = f"{cpu_match.group(1)}%"
        
        # 解析内存使用
        mem_match = re.search(r'Maximum resident set size.*: (\d+)', output)
        if mem_match:
            mem_kb = int(mem_match.group(1))
            if mem_kb > 1024:
                memory_peak = f"{mem_kb // 1024} MB"
            else:
                memory_peak = f"{mem_kb} KB"

        # 上下文切换/页错误/文件系统 I/O
        vol_cs = re.search(r'Voluntary context switches:\s*(\d+)', output)
        if vol_cs:
            cache_info["voluntary_ctx_switches"] = vol_cs.group(1)
        invol_cs = re.search(r'Involuntary context switches:\s*(\d+)', output)
        if invol_cs:
            cache_info["involuntary_ctx_switches"] = invol_cs.group(1)

        maj_pf = re.search(r'Major \(requiring I/O\) page faults:\s*(\d+)', output)
        if maj_pf:
            cache_info["major_page_faults"] = maj_pf.group(1)
        min_pf = re.search(r'Minor \(reclaiming a frame\) page faults:\s*(\d+)', output)
        if min_pf:
            cache_info["minor_page_faults"] = min_pf.group(1)

        fs_in = re.search(r'File system inputs:\s*(\d+)', output)
        if fs_in:
            cache_info["fs_inputs"] = fs_in.group(1)
        fs_out = re.search(r'File system outputs:\s*(\d+)', output)
        if fs_out:
            cache_info["fs_outputs"] = fs_out.group(1)
        
        return ProfilingData(
            total_time=total_time,
            hotspots=[],
            memory_peak=memory_peak,
            cache_info=cache_info
        )
