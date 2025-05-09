# DXF 到 G-code 转换器和模拟器

该项目旨在将 DXF 文件中的二维几何实体（直线、圆弧、圆、多段线等）转换为适用于 CNC 加工或绘图的 G-code，同时提供基于 Matplotlib 的 G-code 路径模拟功能。

## 功能（规划）

- 使用 `ezdxf` 库解析 DXF 文件。
- 支持常见 DXF 实体：
  - LINE（直线）
  - ARC（圆弧）
  - CIRCLE（圆）
  - LWPOLYLINE（轻量多段线）
  - POLYLINE（多段线）
  - SPLINE（样条曲线，近似为线段）
  - ELLIPSE（椭圆，近似为线段或多段圆弧）
- 生成 G-code 输出文件（.gcode）。
- 可配置 G-code 参数（如进给速度、刀具编号、雕刻/切割的 Z 深度）。
- 基本的 2D G-code 路径可视化（使用 `matplotlib`）。

## 前提条件

- Python 3.7+

## 安装

1. 克隆仓库或下载文件。
2. 创建并激活虚拟环境（推荐）：
   ```bash
   python -m venv venv
   # Windows:
   venv\\Scripts\\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 使用（规划）

```bash
python dxf_to_gcode.py <输入_dxf_file> <输出_gcode_file> [选项]
```

可选参数示例：

- `--offset_x X`：在生成 G-code 时应用全局 X 偏移。
- `--offset_y Y`：在生成 G-code 时应用全局 Y 偏移。

## 开发说明

- **DXF 实体处理**：核心逻辑将在 DXF 模型空间中遍历实体。
- **坐标系统**：确保正确处理 DXF 世界坐标系（WCS）和 G-code 坐标系。
- **圆弧转换**：将 DXF 圆弧转换为 G02/G03 命令，通常需要起点、终点和中心点或半径。
- **曲线近似**：将样条和椭圆展平为多段线（短线段序列）用于 G-code 生成。
- **模拟**：模拟器将解析生成的 G-code 并绘制 X-Y 运动路径。
