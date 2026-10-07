# Seeds for ICSE-2025-013 — Java-JNI Cross-Language Static Analysis

> 论文正式标题：**Interactive Cross-Language Pointer Analysis for Resolving Native Code in Java Programs**（ICSE 2025 Distinguished Paper / JNIFER）。

## 下载数据（主机侧，仅数据集）

```bash
chmod +x download_jnifer_subjects.sh
./download_jnifer_subjects.sh
```

| 项 | 值 |
|----|-----|
| 主机路径 | `~/ai_scientist_inputs/shared_datasets/jnifer-subjects` |
| Docker 挂载 | `/shared/jnifer-subjects`（只读） |
| Agent 路径 | `dataset_candidate/jnifer-subjects/` |
| 环境变量 | `JNIFER_SUBJECTS_HOME`, `OPENJDK8_HOME`, `ASPECTJ_HOME`, `LUCENE_HOME`, `TOMCAT_NATIVE_HOME`, `LOG4J_HOME` |

### 体积（压缩包）

| Subject | 约多大 |
|---------|--------|
| OpenJDK 8 (`openjdk8u462-b08.tar.xz`) | **~57 MiB** |
| aspectj-1.6.9 | **~50 MiB** |
| lucene-4.3.0 | **~27 MiB** |
| log4j-1.2.16 | **~2.7 MiB** |
| tomcat-native-1.2.23 | **~0.4 MiB** |
| **合计** | **~140 MiB** |

**不含** JNIFER / JN-Sum / Native-Scanner 工具镜像（那些是 baseline/工具，不是数据集）。

可选 AEC 产物（工具镜像）：https://doi.org/10.5281/zenodo.14897613

## Docker / 容器环境

`task.env` + `seeds/container_setup.sh` 在容器启动时安装：

- **OpenJDK 17**（`java` / `javac`）+ 可选 OpenJDK 8
- **Maven / Ant**
- **GCC / G++ / CMake / Ninja**（C/native / SVF 类构建）
- Python venv：`/opt/icse-2025-013-venv`

| 参数 | 论文设置 | `task.env` |
|------|----------|------------|
| 内存 | 128 GB | `MEMORY=48g` |
| CPU | 未强制 | `CPUS=8` |

## 启动 benchmark

```bash
./download_jnifer_subjects.sh
./run_aiscientist_benchmark.sh run
# 或 ./run_airesearcher_benchmark.sh run
```
