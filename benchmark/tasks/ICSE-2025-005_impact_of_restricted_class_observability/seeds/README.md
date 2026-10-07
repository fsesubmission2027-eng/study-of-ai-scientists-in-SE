# Seeds for ICSE-2025-005 — Class Observability / EvoSuite (SF110)

> 论文正式标题：**Increasing the Effectiveness of Automatically Generated Tests by Improving Class Observability**（ICSE 2025 Distinguished Paper）。

## 下载数据（主机侧）

```bash
chmod +x download_sf110_evosuite.sh
./download_sf110_evosuite.sh
# 可选：只要二进制  FETCH_MODE=bin ./download_sf110_evosuite.sh
# 可选：只要源码    FETCH_MODE=src ./download_sf110_evosuite.sh
```

| 项 | 值 |
|----|-----|
| 主机路径 | `~/ai_scientist_inputs/shared_datasets/sf110-evosuite` |
| Docker 挂载 | `/shared/sf110-evosuite`（只读） |
| Agent 路径 | `dataset_candidate/sf110-evosuite/` |
| 环境变量 | `SF110_EVOSUITE_HOME`, `SF110_HOME`, `EVOSUITE_JAR` |

### 体积（已核对 Content-Length）

| 文件 | URL | 压缩体积 |
|------|-----|----------|
| `SF110-20130704.zip` | https://www.evosuite.org/files/SF110-20130704.zip | **~943 MB**（988,010,008 B） |
| `SF110-20130704-src.zip` | https://www.evosuite.org/files/SF110-20130704-src.zip | **~1014 MB**（1,062,890,473 B） |
| `evosuite-1.2.0.jar` | GitHub release v1.2.0 | **~19 MB** |
| `evosuite-standalone-runtime-1.2.0.jar` | 同上 | **~7 MB** |
| **合计（默认 bin+src+jars）** | — | **约 2.0 GB 压缩包**；解压后再占约 **1–2 GB** |

说明：官网介绍页上的 `wp-content/uploads/...` 链接常 404，请用 **`https://www.evosuite.org/files/`**。

### 论文 100 类子集

SF110 全量约 **110 个项目 / >23K 类**。论文用 **CC > 3** 的 **100 类**（沿用先前研究子集）。该列表 **不在** 公开 zip 内；需：

1. 用圈复杂度过滤自行重建，或  
2. 从 figshare 复现包获取：https://figshare.com/s/46bfa8872f668fafdf66  

## Docker / 容器环境

`task.env` + `seeds/container_setup.sh` 在容器启动时安装：

- **OpenJDK 17**（`java` / `javac`）
- **Maven / Ant**（构建 SF110 工程）
- **unzip / zip**
- Python venv：`/opt/icse-2025-005-venv`（numpy/pandas/scipy/statsmodels 等，用于 Wilcoxon / A12）

| 参数 | 论文设置 | `task.env` |
|------|----------|------------|
| 内存 | 64 GB 整机 | `MEMORY=32g` |
| CPU | 20 核 | `CPUS=8` |
| 搜索预算 | 180 s | 协议见 `benchmark_config.json` |
| 断言超时 | 600 s | 同上 |
| 全量实验 | ~6 天 / 12,000 suites | 按论文协议执行 |

## 启动 benchmark

```bash
./download_sf110_evosuite.sh          # 主机执行一次（约 2GB 下载）
./run_aiscientist_benchmark.sh run    # 或 run_airesearcher_benchmark.sh
```

## 评估协议（默认）

- 算法：**DynaMOSA**
- 配置：baseline / injected getters / recursive assertions / combined
- 指标：**mutation_score**、statement/branch/suite coverage、**A12**
- 约束：注入的 getter **不计入** coverage goals 与 mutant 集合
