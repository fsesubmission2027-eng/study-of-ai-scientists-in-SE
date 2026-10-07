# Seeds for ICSE-2025-004 — THANOS / DBMS Differential Testing (Storage Engine Rotation)

> 论文正式标题：**Thanos: DBMS Bug Detection via Storage Engine Rotation Based Differential Testing**（ICSE 2025 Distinguished Paper）。任务 brief 中的 “Diverse Equivalent Instance Construction” 与同一工作。

## 下载的数据 / 工具（主机侧）

```bash
chmod +x download_dbms_differential_testing_tools.sh
./download_dbms_differential_testing_tools.sh
```

| 项 | 值 |
|----|-----|
| 主机路径 | `~/ai_scientist_inputs/shared_datasets/dbms-differential-testing-tools` |
| Docker 挂载 | `/shared/dbms-differential-testing-tools`（只读） |
| Agent 路径 | `dataset_candidate/dbms-differential-testing-tools/` |
| 环境变量 | `DBMS_DIFFERENTIAL_TESTING_TOOLS_HOME` |

### Git clone 体积（约 **20 MB**）

| 目录 | 仓库 | 体积（depth=1） |
|------|------|----------------|
| `sqlancer/` | https://github.com/sqlancer/sqlancer | ~13 MB |
| `sqlsmith/` | https://github.com/anse1/sqlsmith | ~1 MB |
| `squirrel/` | https://github.com/s3team/Squirrel | ~6 MB |
| `thanos/` | https://github.com/Thanos2024/Thanos | **当前常 404**，需向作者索取或按论文复现 |

### 不在 clone 里、需在容器内构建（体积大）

| 组件 | 来源 | 预估磁盘 |
|------|------|----------|
| MySQL 8.0.x 源码 + AFL++ 构建 | https://github.com/mysql/mysql-server | **5–15 GB** |
| MariaDB 10.x 源码 + 构建 | https://github.com/MariaDB/server | **5–15 GB** |
| Percona Server 8.0.x 源码 + 构建 | https://github.com/percona/percona-server | **5–15 GB** |
| 三套 DBMS 合计 | — | **约 15–45 GB**（视构建选项而定） |

**没有传统“静态数据集”**：SQL 测试用例由 THANOS / 基线 fuzzer **运行时生成**。存储引擎 feature 等价表属于 THANOS artifact（论文称见 THANOS website）。

## Docker / 容器环境

`task.env` + `seeds/container_setup.sh` 在容器启动时安装：

- **AFL++**（`afl-fuzz`, `afl-clang-fast`）— 论文用其收集 branch coverage
- **OpenJDK 17 + Gradle** — 构建 / 运行 SQLancer
- **bison / flex / cmake** — THANOS AST 与 DBMS 编译
- **unixodbc, libmysqlclient-dev** — ODBC 客户端与 MySQL 协议工具链
- Python venv：`/opt/icse-2025-004-venv`

资源建议（对齐论文）：

| 参数 | 论文设置 | `task.env` |
|------|----------|------------|
| 内存 | 40 GiB / DBMS 实例 | `MEMORY=40g` |
| CPU | 5 核 / 实例 | `CPUS=8`（宿主机容器上限） |
| 单次实验 | 24 h / (工具, DBMS) | `TIMEOUT_SEC=2592000`（30 天总预算） |

论文在 **Ubuntu 20.04** 上每个 DBMS 实例跑在独立 Docker 中；benchmark 容器内可直接起 `mysqld` 做 smoke test，完整复现可用嵌套 Docker 或宿主机多容器。

## 启动 benchmark

```bash
./download_dbms_differential_testing_tools.sh   # 主机执行一次
./run_aiscientist_benchmark.sh run              # 或 run_airesearcher_benchmark.sh
```

## 评估协议（默认）

- **3** 个 DBMS（MySQL, MariaDB, Percona）
- **4** 个工具（THANOS + SQLancer + SQLsmith + SQUIRREL）
- 每个组合 **24 小时**
- 指标：**branch coverage**、**confirmed bug count**；RQ3 可加 triggered features 比例
