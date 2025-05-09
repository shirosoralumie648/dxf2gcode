import ezdxf
import math
import argparse
import sys # Ensure sys is imported
import os
import re
import plotly.graph_objects as go
import plotly.colors as pcolors

# 使用Plotly替代Matplotlib

# Default G-code parameters (can be overridden by command-line arguments)
DEFAULT_FEED_RATE_XY = 300.0  # mm/min or units/min
DEFAULT_FEED_RATE_Z = 100.0   # mm/min or units/min
DEFAULT_SAFE_Z = 5.0         # Z height for rapid moves
DEFAULT_CUT_Z = -0.3         # Z depth for cutting (relative to Z=0 on material surface)


def generate_gcode_header(safe_z):
    return [
        "G21",          # Set units to millimeters
        "G90",          # Absolute programming
        "G17",          # Select XY plane
        "M3 S1000",     # Spindle on, 1000 RPM (example)
        f"G00 Z{safe_z:.3f}"  # Rapid move to safe Z
    ]

def generate_gcode_footer(safe_z):
    return [
        f"G00 Z{safe_z:.3f}", # Retract to safe Z
        "M5",           # Spindle off
        "G00 X0 Y0",    # Go to machine home (optional)
        "M2"            # Program end
    ]

def line_to_gcode(entity, current_pos, feed_rate_xy, feed_rate_z, safe_z, cut_z):
    gcode_lines = []
    start_point = entity.dxf.start
    end_point = entity.dxf.end

    # 1. Rapid move to above the start point of the line
    if current_pos is None or not (math.isclose(current_pos[0], start_point.x) and math.isclose(current_pos[1], start_point.y)):
        gcode_lines.append(f"G00 X{start_point.x:.3f} Y{start_point.y:.3f}")
    
    # 2. Plunge to cutting depth
    gcode_lines.append(f"G01 Z{cut_z:.3f} F{feed_rate_z:.1f}")
    
    # 3. Linear move to the end point of the line
    gcode_lines.append(f"G01 X{end_point.x:.3f} Y{end_point.y:.3f} F{feed_rate_xy:.1f}")
    
    # 4. Retract to safe Z (optional, can be done after all paths of a layer)
    gcode_lines.append(f"G00 Z{safe_z:.3f}")
    
    current_pos = (end_point.x, end_point.y, safe_z)
    return gcode_lines, current_pos


def arc_to_gcode(entity, current_pos, feed_rate_xy, feed_rate_z, safe_z, cut_z):
    gcode_lines = []
    center = entity.dxf.center
    radius = entity.dxf.radius
    start_angle = entity.dxf.start_angle
    end_angle = entity.dxf.end_angle
    
    # 规范化角度至0-360度范围
    while start_angle < 0: start_angle += 360
    while start_angle >= 360: start_angle -= 360
    while end_angle < 0: end_angle += 360
    while end_angle >= 360: end_angle -= 360
    
    # 计算起始点和终点坐标
    start_angle_rad = math.radians(start_angle)
    end_angle_rad = math.radians(end_angle)
    start_x = center.x + radius * math.cos(start_angle_rad)
    start_y = center.y + radius * math.sin(start_angle_rad)
    end_x = center.x + radius * math.cos(end_angle_rad)
    end_y = center.y + radius * math.sin(end_angle_rad)
    
    # 计算中心相对于起点的偏移
    i_offset = center.x - start_x
    j_offset = center.y - start_y
    
    # 打印原始角度信息以及起点和终点
    print(f"  Arc original: start_angle={entity.dxf.start_angle:.2f}, end_angle={entity.dxf.end_angle:.2f}")
    print(f"  Arc normalized: start_angle={start_angle:.2f}, end_angle={end_angle:.2f}")
    print(f"  Arc endpoints: start=({start_x:.2f},{start_y:.2f}), end=({end_x:.2f},{end_y:.2f})")
    
    # DXF ARC 定义：从 start_angle 到 end_angle 逆时针。
    ccw_angle = (end_angle - start_angle) % 360
    print(f"  CCW angle: {ccw_angle:.2f}°")
    # 如果之前 G03 (CCW 指令) 导致方向错误，则尝试 G02 (CW 指令)
    # 来正确表示 DXF 中定义的 CCW 圆弧。
    arc_command = "G02" # 注意：这里改为 G02
     
    # 判断是否分段（大于180°需分两段）
    if ccw_angle <= 180:
        print(f"  Minor arc ({ccw_angle:.2f}°), single segment, command {arc_command}")
        segments = [(end_x, end_y, i_offset, j_offset)]
    else:
        print(f"  Major arc ({ccw_angle:.2f}°), splitting at 180°, command {arc_command}")
        # 分割点依然是沿 CCW 路径前进 180 度
        mid_angle = (start_angle + 180) % 360
        mid_rad = math.radians(mid_angle)
        mid_x = center.x + radius * math.cos(mid_rad)
        mid_y = center.y + radius * math.sin(mid_rad)
        i1, j1 = i_offset, j_offset
        i2, j2 = center.x - mid_x, center.y - mid_y
        segments = [(mid_x, mid_y, i1, j1), (end_x, end_y, i2, j2)]
    # 此行已在分段逻辑中通过新的print语句覆盖，或可删除
    # print(f"  G-code command: {arc_command}, segments: {len(segments)}") 
 
    # 1. 快速定位到弧的起始点上方
    if current_pos is None or not (math.isclose(current_pos[0], start_x) and math.isclose(current_pos[1], start_y)):
        gcode_lines.append(f"G00 X{start_x:.3f} Y{start_y:.3f}")
    
    # 2. 下刀到切削深度
    gcode_lines.append(f"G01 Z{cut_z:.3f} F{feed_rate_z:.1f}")
    
    # 3. 弧形移动，可能分段
    for x, y, i_off, j_off in segments:
        gcode_lines.append(f"{arc_command} X{x:.3f} Y{y:.3f} I{i_off:.3f} J{j_off:.3f} F{feed_rate_xy:.1f}")
    
    # 4. 提升到安全高度
    gcode_lines.append(f"G00 Z{safe_z:.3f}")
    
    # 更新当前位置
    current_pos = (end_x, end_y, safe_z)
    return gcode_lines, current_pos


def circle_to_gcode(entity, current_pos, feed_rate_xy, feed_rate_z, safe_z, cut_z):
    gcode_lines = []
    center = entity.dxf.center
    radius = entity.dxf.radius

    # Define points for two semi-circles
    # Start point of 1st semi-circle (and end point of 2nd)
    p1_start_x = center.x - radius
    p1_start_y = center.y

    # Midpoint (end point of 1st semi-circle, start point of 2nd)
    p1_end_x = center.x + radius
    p1_end_y = center.y 
    # (p2_start_x, p2_start_y are the same as p1_end_x, p1_end_y)

    # End point of 2nd semi-circle (same as p1_start_x, p1_start_y)
    # p2_end_x = p1_start_x
    # p2_end_y = p1_start_y

    # G-code for the first semi-circle (e.g., G02 - clockwise, lower half)
    # Center relative to P1_start for the first arc
    i1_offset = center.x - p1_start_x # This will be 'radius'
    j1_offset = center.y - p1_start_y # This will be 0

    # G-code for the second semi-circle (e.g., G02 - clockwise, upper half)
    # Center relative to P1_end (which is P2_start) for the second arc
    i2_offset = center.x - p1_end_x # This will be '-radius'
    j2_offset = center.y - p1_end_y # This will be 0
    
    # 1. Rapid move to above the start point of the first semi-circle
    if current_pos is None or not (math.isclose(current_pos[0], p1_start_x) and math.isclose(current_pos[1], p1_start_y)):
        gcode_lines.append(f"G00 X{p1_start_x:.3f} Y{p1_start_y:.3f}")
    
    # 2. Plunge to cutting depth
    gcode_lines.append(f"G01 Z{cut_z:.3f} F{feed_rate_z:.1f}")
    
    # 3. First semi-circle (e.g., bottom half, CW)
    # G02 X<end_x> Y<end_y> I<center_x_offset_from_start> J<center_y_offset_from_start>
    gcode_lines.append(f"G02 X{p1_end_x:.3f} Y{p1_end_y:.3f} I{i1_offset:.3f} J{j1_offset:.3f} F{feed_rate_xy:.1f}")
    
    # 4. Second semi-circle (e.g., top half, CW)
    # Current position is now p1_end_x, p1_end_y
    gcode_lines.append(f"G02 X{p1_start_x:.3f} Y{p1_start_y:.3f} I{i2_offset:.3f} J{j2_offset:.3f} F{feed_rate_xy:.1f}")

    # 5. Retract to safe Z
    gcode_lines.append(f"G00 Z{safe_z:.3f}")
    
    current_pos = (p1_start_x, p1_start_y, safe_z) # End position after full circle is back at its start
    return gcode_lines, current_pos


def lwpolyline_to_gcode(entity, current_pos, feed_rate_xy, feed_rate_z, safe_z, cut_z):
    gcode_lines = []
    # ezdxf lwpolyline points are (x, y, start_width, end_width, bulge)
    # We are only interested in x, y for now (indices 0 and 1)
    points = list(entity.get_points(format='xyseb')) # format provides (x,y,start_width,end_width,bulge)

    if not points:
        return [], current_pos

    start_x, start_y, _, _, start_bulge = points[0]

    # 1. Rapid move to above the start point of the polyline
    if current_pos is None or not (math.isclose(current_pos[0], start_x) and math.isclose(current_pos[1], start_y)):
        gcode_lines.append(f"G00 X{start_x:.3f} Y{start_y:.3f}")
    
    # 2. Plunge to cutting depth
    gcode_lines.append(f"G01 Z{cut_z:.3f} F{feed_rate_z:.1f}")
    current_x, current_y = start_x, start_y
    current_pos = (current_x, current_y, cut_z) # update current_pos to be at cut depth

    # Iterate through segments (from point i to point i+1)
    for i in range(len(points) - 1):
        px1, py1, _, _, bulge = points[i]
        px2, py2, _, _, _ = points[i+1]

        if bulge != 0:
            # TODO: Implement bulge to arc conversion
            # For now, we print a warning and skip arc segments
            print(f"    LWPOLYLINE segment from ({px1:.2f}, {py1:.2f}) to ({px2:.2f}, {py2:.2f}) has a bulge ({bulge:.2f}) - ARC SEGMENT SKIPPED.")
            # As a fallback, we could rapid move to the start of the next segment if we skip an arc
            # For now, we'll just continue, which means the tool stays at the end of the last processed segment.
            # To ensure the next straight segment starts correctly, we might need a G00 to px2, py2 if we are not already there
            # However, if the next segment is also a bulge, this logic would be complex.
            # Simplest for now: if we hit a bulge, we might have an issue with the next G01 if tool path is broken.
            # Let's assume for now that if a bulge is skipped, the next segment is a line that starts from the bulge's end point
            # This requires getting the end point of the arc represented by the bulge.
            # This is complex, so for V1, we just warn and the G-code might be incomplete for polylines with arcs.
            # A better V1 for bulges is to treat them as straight lines between their vertex points.
            gcode_lines.append(f"; WARNING: LWPOLYLINE bulge segment from ({px1:.2f}, {py1:.2f}) to ({px2:.2f}, {py2:.2f}) treated as straight line.")
            gcode_lines.append(f"G01 X{px2:.3f} Y{py2:.3f} F{feed_rate_xy:.1f}") # Treat bulge as straight line
        else:
            # Straight line segment
            gcode_lines.append(f"G01 X{px2:.3f} Y{py2:.3f} F{feed_rate_xy:.1f}")
        
        current_x, current_y = px2, py2
        current_pos = (current_x, current_y, cut_z)

    # If the polyline is closed and the last segment was a line (not a skipped bulge leading to it),
    # and it connects back to the very first point, no extra move is needed.
    # ezdxf handles 'closed' property separately. get_points() gives all points including closing one if closed.

    # Retract to safe Z after the entire polyline is done
    gcode_lines.append(f"G00 Z{safe_z:.3f}")
    current_pos = (current_x, current_y, safe_z)

    return gcode_lines, current_pos


def get_arc_points(current_x, current_y, target_x, target_y, i_offset, j_offset, is_clockwise, num_segments=20):
    """Helper function to generate points along an arc for plotting."""
    center_x = current_x + i_offset
    center_y = current_y + j_offset
    radius = math.sqrt(i_offset**2 + j_offset**2)

    # Ensure radius is not zero to avoid division by zero in atan2 or elsewhere
    if math.isclose(radius, 0.0):
        return [(current_x, current_y), (target_x, target_y)] # Treat as a line if radius is zero

    start_angle = math.atan2(current_y - center_y, current_x - center_x)
    end_angle = math.atan2(target_y - center_y, target_x - center_x)

    if is_clockwise: # G02
        if end_angle >= start_angle:
            end_angle -= 2 * math.pi
    else: # G03
        if end_angle <= start_angle:
            end_angle += 2 * math.pi

    # Handle potential full circle if start and end points are identical for the arc command
    # This case is more for G-code like G02 I10 J0 (full circle from current point)
    # If target_x, target_y are same as current_x, current_y, it's a full circle.
    if math.isclose(current_x, target_x) and math.isclose(current_y, target_y):
        if is_clockwise:
            end_angle = start_angle - 2 * math.pi
        else:
            end_angle = start_angle + 2 * math.pi
            
    points = []
    for k in range(num_segments + 1):
        angle = start_angle + (end_angle - start_angle) * k / num_segments
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        points.append((x, y))
    return points


def simulate_gcode(gcode_filepath, offset_x=0.0, offset_y=0.0, start_x=0.0, start_y=0.0, end_x=0.0, end_y=0.0):
    """Simulate G-code by plotting the toolpath using Plotly."""
    print("[SIM] simulate_gcode started."); sys.stdout.flush()
    try:
        print(f"[SIM] Attempting to open G-code file: {gcode_filepath}"); sys.stdout.flush()
        
        # 打开G代码文件
        with open(gcode_filepath, 'r') as f:
            gcode_lines = f.readlines()
        print("[SIM] G-code file opened successfully."); sys.stdout.flush()
        
        # 初始化绘图数据
        fig = go.Figure()
        current_pos = {'x': 0, 'y': 0, 'z': 0}
        
        # 按Z高度分段收集轨迹
        segments_by_z = {}  # z值 -> {'x':[], 'y':[]}
        
        # 处理每行G代码
        for i, line in enumerate(gcode_lines):
            line = line.strip()
            if not line or line.startswith(';'):
                continue  # 跳过空行和注释
                
            print(f"[SIM] Processing line {i+1}: {line}"); sys.stdout.flush()
            
            # 提取G代码命令和参数
            # 示例行: G01 X10.0 Y20.0 Z-1.0 F100.0
            line_parts = line.split()
            if not line_parts:
                continue
                
            command = line_parts[0]
            print(f"[SIM] Command: {command}"); sys.stdout.flush()
                
            # 解析坐标和参数
            coords = {'x': current_pos['x'], 'y': current_pos['y'], 'z': current_pos['z'], 'i': 0, 'j': 0}
            for part in line_parts[1:]:
                if part.startswith('X'):
                    coords['x'] = float(part[1:])
                elif part.startswith('Y'):
                    coords['y'] = float(part[1:])
                elif part.startswith('Z'):
                    coords['z'] = float(part[1:])
                elif part.startswith('I'):
                    coords['i'] = float(part[1:])
                elif part.startswith('J'):
                    coords['j'] = float(part[1:])
            
            print(f"[SIM] Parsed Coords: X{coords['x']} Y{coords['y']} Z{coords['z']} I{coords['i']} J{coords['j']}"); sys.stdout.flush()
            
            # 根据G代码命令绘制
            if command in ['G0', 'G00']:
                print(f"[SIM] Plotting G00 from ({current_pos['x']:.2f},{current_pos['y']:.2f}) to ({coords['x']:.2f},{coords['y']:.2f})"); sys.stdout.flush()
                # 按Z分段记录
                z_level = current_pos['z']
                seg = segments_by_z.setdefault(z_level, {'x':[], 'y':[]})
                seg['x'].extend([current_pos['x'], coords['x'], None])
                seg['y'].extend([current_pos['y'], coords['y'], None])
                print("[SIM] G00 plotted."); sys.stdout.flush()
            
            elif command in ['G1', 'G01']:
                print(f"[SIM] Plotting G01 from ({current_pos['x']:.2f},{current_pos['y']:.2f}) to ({coords['x']:.2f},{coords['y']:.2f})"); sys.stdout.flush()
                # 按Z分段记录
                z_level = current_pos['z']
                seg = segments_by_z.setdefault(z_level, {'x':[], 'y':[]})
                seg['x'].extend([current_pos['x'], coords['x'], None])
                seg['y'].extend([current_pos['y'], coords['y'], None])
                print("[SIM] G01 plotted."); sys.stdout.flush()
            
            elif command in ['G2', 'G02', 'G3', 'G03']:
                center_x = current_pos['x'] + coords['i']
                center_y = current_pos['y'] + coords['j']
                
                # 计算圆弧属性
                radius = math.sqrt(coords['i']**2 + coords['j']**2)
                start_angle = math.atan2(current_pos['y'] - center_y, current_pos['x'] - center_x)
                end_angle = math.atan2(coords['y'] - center_y, coords['x'] - center_x)
                
                # 调整G3/G03（逆时针）的角度
                if command in ['G3', 'G03']:
                    if end_angle > start_angle:
                        end_angle -= 2 * math.pi
                else:  # G2/G02（顺时针）
                    if end_angle < start_angle:
                        end_angle += 2 * math.pi
                
                # 生成圆弧上的点用于绘图
                num_points = 21  # 用于圆弧的点数
                print(f"[SIM] Calculating arc points for {command} from ({current_pos['x']:.2f},{current_pos['y']:.2f}) to ({coords['x']:.2f},{coords['y']:.2f}) with I{coords['i']:.2f} J{coords['j']:.2f}"); sys.stdout.flush()
                
                arc_x = []
                arc_y = []
                
                if command in ['G2', 'G02']:  # 顺时针
                    if end_angle <= start_angle:
                        end_angle += 2 * math.pi
                    theta_values = [start_angle + (end_angle - start_angle) * i / (num_points - 1) for i in range(num_points)]
                    for theta in theta_values:
                        arc_x.append(center_x + radius * math.cos(theta))
                        arc_y.append(center_y + radius * math.sin(theta))
                    # 添加None以分隔多个圆弧段
                    arc_x.append(None)
                    arc_y.append(None)
                    # 按Z分段记录圆弧
                    z_level = current_pos['z']
                    seg = segments_by_z.setdefault(z_level, {'x':[], 'y':[]})
                    seg['x'].extend(arc_x)
                    seg['y'].extend(arc_y)
                else:  # G3/G03逆时针
                    if end_angle >= start_angle:
                        end_angle -= 2 * math.pi
                    theta_values = [start_angle + (end_angle - start_angle) * i / (num_points - 1) for i in range(num_points)]
                    for theta in theta_values:
                        arc_x.append(center_x + radius * math.cos(theta))
                        arc_y.append(center_y + radius * math.sin(theta))
                    # 添加None以分隔多个圆弧段
                    arc_x.append(None)
                    arc_y.append(None)
                    # 按Z分段记录圆弧
                    z_level = current_pos['z']
                    seg = segments_by_z.setdefault(z_level, {'x':[], 'y':[]})
                    seg['x'].extend(arc_x)
                    seg['y'].extend(arc_y)
                
                print(f"[SIM] Arc points calculated: {len(arc_x)-1} points."); sys.stdout.flush()
                print("[SIM] Arc plotted."); sys.stdout.flush()
            
            # 更新当前位置
            current_pos['x'] = coords['x']
            current_pos['y'] = coords['y']
            current_pos['z'] = coords['z']
            
            print(f"[SIM] End of line {i+1} processing. New current_pos: X{current_pos['x']:.2f} Y{current_pos['y']:.2f} Z{current_pos['z']:.2f}"); sys.stdout.flush()
        
        # 根据Z高度使用Viridis连续色带显示所有轨迹（包括快速移动和切削移动）
        z_levels = sorted(segments_by_z.keys())
        colorscale = pcolors.sequential.Viridis
        n = len(z_levels)
        for idx_z, z_level in enumerate(z_levels):
            seg = segments_by_z[z_level]
            if not seg['x']:
                continue
            ratio = idx_z/(n-1) if n>1 else 0
            cs_idx = int(ratio*(len(colorscale)-1))
            color = colorscale[cs_idx]
            fig.add_trace(go.Scatter(x=seg['x'], y=seg['y'], mode='lines',
                                    line=dict(color=color, width=2),
                                    name=f'Z={z_level:.3f}', showlegend=True))
        
        # 设置图表属性
        fig.update_layout(
            title=f"G-code路径模拟 - {os.path.basename(gcode_filepath)}",
            xaxis_title="X轴 (mm)",
            yaxis_title="Y轴 (mm)",
            legend_title="G代码指令",
            autosize=True,
            width=1000,
            height=800,
            showlegend=True,
            plot_bgcolor='white'
        )
        
        # 保持XY轴1:1比例
        fig.update_layout(yaxis=dict(
            scaleanchor="x",
            scaleratio=1,
        ))
        
        # 添加网格线
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgrey')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgrey')
        
        # === 1. 收集所有刀具运动点 ===
        tool_path_points = []  # [[x, y], ...]
        cur_x, cur_y, cur_z = 0, 0, 0
        for i, line in enumerate(gcode_lines):
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            line_parts = line.split()
            if not line_parts:
                continue
            command = line_parts[0]
            coords = {'x': cur_x, 'y': cur_y, 'z': cur_z, 'i': 0, 'j': 0}
            for part in line_parts[1:]:
                if part.startswith('X'):
                    coords['x'] = float(part[1:])
                elif part.startswith('Y'):
                    coords['y'] = float(part[1:])
                elif part.startswith('Z'):
                    coords['z'] = float(part[1:])
                elif part.startswith('I'):
                    coords['i'] = float(part[1:])
                elif part.startswith('J'):
                    coords['j'] = float(part[1:])
            # 只记录XY平面运动
            if command in ['G0', 'G00', 'G1', 'G01']:
                # 直线插补：直接起点到终点
                tool_path_points.append([coords['x'], coords['y']])
                cur_x, cur_y, cur_z = coords['x'], coords['y'], coords['z']
            elif command in ['G2', 'G02', 'G3', 'G03']:
                # 圆弧插补：插值为多个点
                center_x = cur_x + coords['i']
                center_y = cur_y + coords['j']
                radius = math.sqrt(coords['i']**2 + coords['j']**2)
                start_angle = math.atan2(cur_y - center_y, cur_x - center_x)
                end_angle = math.atan2(coords['y'] - center_y, coords['x'] - center_x)
                num_points = 21
                if command in ['G3', 'G03']:
                    if end_angle > start_angle:
                        end_angle -= 2 * math.pi
                else:
                    if end_angle < start_angle:
                        end_angle += 2 * math.pi
                theta_values = [start_angle + (end_angle - start_angle) * i / (num_points - 1) for i in range(num_points)]
                for theta in theta_values:
                    px = center_x + radius * math.cos(theta)
                    py = center_y + radius * math.sin(theta)
                    tool_path_points.append([px, py])
                cur_x, cur_y, cur_z = coords['x'], coords['y'], coords['z']
            # 其他命令不计入动画轨迹
        # 防止轨迹为空
        if not tool_path_points:
            tool_path_points = [[0, 0]]
        # Apply custom start point translation
        if start_x != 0.0 or start_y != 0.0:
            dx = start_x - tool_path_points[0][0]
            dy = start_y - tool_path_points[0][1]
            tool_path_points = [[p[0] + dx, p[1] + dy] for p in tool_path_points]
        # Override end point to user-specified coordinates
        tool_path_points[-1] = [end_x, end_y]
        import json
        tool_path_points_json = json.dumps(tool_path_points)
        # Add markers for tool start and end points
        if tool_path_points:
            sx, sy = tool_path_points[0]
            ex, ey = tool_path_points[-1]
            fig.add_trace(go.Scatter(x=[sx], y=[sy], mode='markers', marker=dict(color='green', size=12), name='Start Point'))
            fig.add_trace(go.Scatter(x=[ex], y=[ey], mode='markers', marker=dict(color='red', size=12), name='End Point'))
        # === 2. 美化前端并加入动画 ===
        html_filename = 'simulation_plot.html'
        try:
            print(f"[SIM] Saving interactive plot to {html_filename}"); sys.stdout.flush()
            plot_html = fig.to_html(include_plotlyjs='cdn', full_html=False, default_height='700px', div_id='plot')
            custom_html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>G-code 仿真</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/codemirror.min.css">
  <style>body{background:#f8f9fa;} .CodeMirror{height:100%;}</style>
</head>
<body>
<div class="container py-4">
  <h1 class="mb-4">G-code 路径可视化与仿真</h1>
  <form action="/convert" method="post" class="row mb-3">
    <input type="hidden" name="filename" value="''' + os.path.splitext(os.path.basename(gcode_filepath))[0] + '''">
    <div class="col-6">
      <label>Start X (mm):</label>
      <input name="start_x" type="number" class="form-control" step="0.01" value="''' + str(start_x) + '''">
    </div>
    <div class="col-6">
      <label>Start Y (mm):</label>
      <input name="start_y" type="number" class="form-control" step="0.01" value="''' + str(start_y) + '''">
    </div>
    <div class="col-6">
      <label>End X (mm):</label>
      <input name="end_x" type="number" class="form-control" step="0.01" value="''' + str(end_x) + '''">
    </div>
    <div class="col-6">
      <label>End Y (mm):</label>
      <input name="end_y" type="number" class="form-control" step="0.01" value="''' + str(end_y) + '''">
    </div>
    <div class="col-6">
      <label>X 偏移 (mm):</label>
      <input name="offset_x" type="number" class="form-control" step="0.01" value="''' + str(offset_x) + '''">
    </div>
    <div class="col-6">
      <label>Y 偏移 (mm):</label>
      <input name="offset_y" type="number" class="form-control" step="0.01" value="''' + str(offset_y) + '''">
    </div>
    <div class="col-12 d-flex justify-content-between mt-2">
      <button type="submit" class="btn btn-primary">更新仿真</button>
      <a href="/download?filename=''' + os.path.splitext(os.path.basename(gcode_filepath))[0] + '''" class="btn btn-success">下载 G-code</a>
    </div>
  </form>
  <div class="row mb-3">
    <div class="col-12">
      ''' + plot_html + '''
    </div>
  </div>
  <div class="row">
    <div class="col-12">
      <h5>G-code 编辑</h5>
      <textarea id="gcode_editor" class="form-control mb-2" rows="20">''' + ''.join(gcode_lines) + '''</textarea>
    </div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/mode/gcode/gcode.min.js"></script>
<script>
  window.toolPathPoints = ''' + tool_path_points_json + ''';
  window.originalToolPathPoints = JSON.parse(JSON.stringify(window.toolPathPoints));
</script>
<div class="row mb-3">
  <div class="col-12">
    <button id="prevBtn" class="btn btn-secondary me-2">上一步</button>
    <button id="playBtn" class="btn btn-primary me-2">播放</button>
    <button id="nextBtn" class="btn btn-secondary">下一步</button>
  </div>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {
  var pts = window.toolPathPoints;
  var idx = 0;
  var gd = document.getElementById('plot');
  var animTrace = { x:[pts[0][0]], y:[pts[0][1]], mode:'markers', marker:{color:'blue', size:12}, name:'Animation' };
  Plotly.addTraces(gd, animTrace).then(function() {
    var animIndex = gd.data.length - 1;
    function update() { var pt = pts[idx]; Plotly.restyle(gd, {'x': [[pt[0]]], 'y': [[pt[1]]] }, [animIndex]); }
    document.getElementById('nextBtn').onclick = function() { if (idx < pts.length-1) { idx++; update(); } };
    document.getElementById('prevBtn').onclick = function() { if (idx > 0) { idx--; update(); } };
    var interval = null;
    document.getElementById('playBtn').onclick = function() {
      if (interval) { clearInterval(interval); interval = null; this.textContent = '播放'; }
      else { this.textContent = '暂停'; interval = setInterval(function() { if (idx < pts.length-1) { idx++; update(); } else { clearInterval(interval); interval = null; document.getElementById('playBtn').textContent = '播放'; } }, 200); }
    };
  });
});
</script>
 '''
            # 写入自定义HTML
            with open(html_filename, 'w', encoding='utf-8') as f:
                f.write(custom_html)
            print(f"[SIM] Simulation plot saved to {html_filename}"); sys.stdout.flush()
            print(f"[SIM] You can open this HTML file in any web browser to view and interact with the plot."); sys.stdout.flush()
        except Exception as e:
            print(f"[SIM] Error saving interactive plot: {e}"); sys.stdout.flush()
            
        print("[SIM] simulate_gcode finished successfully."); sys.stdout.flush()
    except Exception as e:
        print(f"[SIM] Error in simulate_gcode: {e}"); sys.stdout.flush()


def dxf_to_gcode(dxf_filepath, gcode_filepath, feed_rate_xy, feed_rate_z, safe_z, cut_z, offset_x=0.0, offset_y=0.0, start_x=0.0, start_y=0.0, end_x=0.0, end_y=0.0):
    try:
        doc = ezdxf.readfile(dxf_filepath)
        msp = doc.modelspace()
    except IOError:
        print(f"Error: Cannot open DXF file: {dxf_filepath}")
        return
    except ezdxf.DXFStructureError:
        print(f"Error: Invalid or corrupt DXF file: {dxf_filepath}")
        return

    gcode = generate_gcode_header(safe_z)
    current_pos = None # (x,y,z) - tracks the current tool position

    print(f"Processing DXF entities from {dxf_filepath}...")
    entities_processed = 0
    for entity in msp:
        entity_gcode = []
        if entity.dxftype() == 'LINE':
            print(f"  Found LINE from ({entity.dxf.start.x:.2f}, {entity.dxf.start.y:.2f}) to ({entity.dxf.end.x:.2f}, {entity.dxf.end.y:.2f})")
            entity_gcode, current_pos = line_to_gcode(entity, current_pos, feed_rate_xy, feed_rate_z, safe_z, cut_z)
            entities_processed += 1
        elif entity.dxftype() == 'ARC':
            print(f"  Found ARC center=({entity.dxf.center.x:.2f}, {entity.dxf.center.y:.2f}), R={entity.dxf.radius:.2f}, "
                  f"StartAngle={entity.dxf.start_angle:.2f}, EndAngle={entity.dxf.end_angle:.2f}")
            entity_gcode, current_pos = arc_to_gcode(entity, current_pos, feed_rate_xy, feed_rate_z, safe_z, cut_z)
            entities_processed += 1
        elif entity.dxftype() == 'CIRCLE':
            print(f"  Found CIRCLE center=({entity.dxf.center.x:.2f}, {entity.dxf.center.y:.2f}), R={entity.dxf.radius:.2f}")
            entity_gcode, current_pos = circle_to_gcode(entity, current_pos, feed_rate_xy, feed_rate_z, safe_z, cut_z)
            entities_processed +=1
        elif entity.dxftype() == 'LWPOLYLINE':
            print(f"  Found LWPOLYLINE with {len(list(entity.get_points(format='xyseb')))} points.")
            entity_gcode, current_pos = lwpolyline_to_gcode(entity, current_pos, feed_rate_xy, feed_rate_z, safe_z, cut_z)
            entities_processed +=1
        
        if entity_gcode:
            gcode.extend(entity_gcode)

    gcode.extend(generate_gcode_footer(safe_z))

    # Apply global XY translation offsets
    if offset_x or offset_y:
        translated = []  # will hold offset-adjusted lines
        for line in gcode:
            new_line = line
            if 'X' in new_line:
                new_line = re.sub(r'X([-+]?\d*\.?\d+)', lambda m: f"X{float(m.group(1))+offset_x:.3f}", new_line)
            if 'Y' in new_line:
                new_line = re.sub(r'Y([-+]?\d*\.?\d+)', lambda m: f"Y{float(m.group(1))+offset_y:.3f}", new_line)
            translated.append(new_line)
        gcode = translated

    # Custom start/end G-code adjustments (exclude footer)
    footer = generate_gcode_footer(safe_z)
    pre_gcode = gcode[:-len(footer)]
    # update first XY move
    for i, line in enumerate(pre_gcode):
        if 'X' in line and 'Y' in line:
            pre_gcode[i] = re.sub(r'X([-+]?\d*\.?\d+)', f"X{start_x:.3f}", pre_gcode[i])
            pre_gcode[i] = re.sub(r'Y([-+]?\d*\.?\d+)', f"Y{start_y:.3f}", pre_gcode[i])
            break
    # update last XY move
    for i in range(len(pre_gcode)-1, -1, -1):
        if 'X' in pre_gcode[i] and 'Y' in pre_gcode[i]:
            pre_gcode[i] = re.sub(r'X([-+]?\d*\.?\d+)', f"X{end_x:.3f}", pre_gcode[i])
            pre_gcode[i] = re.sub(r'Y([-+]?\d*\.?\d+)', f"Y{end_y:.3f}", pre_gcode[i])
            break
    gcode = pre_gcode + footer

    try:
        with open(gcode_filepath, 'w') as f:
            for line in gcode:
                f.write(line + '\n')
        print(f"Successfully converted {entities_processed} entities and saved G-code to: {gcode_filepath}")
    except IOError:
        print(f"Error: Cannot write G-code file: {gcode_filepath}")


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Convert DXF to G-code')
    parser.add_argument('input_file', help='Input DXF file path')
    parser.add_argument('output_file', help='Output G-code file path')
    parser.add_argument('--feedrate-xy', type=float, default=DEFAULT_FEED_RATE_XY, help='XY plane feedrate (mm/min)')
    parser.add_argument('--feedrate-z', type=float, default=DEFAULT_FEED_RATE_Z, help='Z axis feedrate (mm/min)')
    parser.add_argument('--safe-z', type=float, default=DEFAULT_SAFE_Z, help='Safe Z height for rapid moves')
    parser.add_argument('--cut-z', type=float, default=DEFAULT_CUT_Z, help='Z height for cutting')
    parser.add_argument('--offset-x', type=float, default=0.0, help='Global X offset')
    parser.add_argument('--offset-y', type=float, default=0.0, help='Global Y offset')
    parser.add_argument('--simulate', action='store_true', help='Simulate the G-code path (currently disabled due to Matplotlib issues)')
    parser.add_argument('--start-x', type=float, default=0.0, help='Custom start X coordinate')
    parser.add_argument('--start-y', type=float, default=0.0, help='Custom start Y coordinate')
    parser.add_argument('--end-x', type=float, default=0.0, help='Custom end X coordinate')
    parser.add_argument('--end-y', type=float, default=0.0, help='Custom end Y coordinate')
    args = parser.parse_args()
    
    try:
        # Print parsed arguments
        print(f"Input file: {args.input_file}")
        print(f"Output file: {args.output_file}")
        print(f"Feed rate XY: {args.feedrate_xy}")
        print(f"Feed rate Z: {args.feedrate_z}")
        print(f"Safe Z: {args.safe_z}")
        print(f"Cut Z: {args.cut_z}")
        print(f"Offset X: {args.offset_x}")
        print(f"Offset Y: {args.offset_y}")
        print(f"Simulation: {'Requested (but will be skipped)' if args.simulate else 'Disabled'}")
        print(f"Start X: {args.start_x}")
        print(f"Start Y: {args.start_y}")
        print(f"End X: {args.end_x}")
        print(f"End Y: {args.end_y}")
        
        # Core functionality: Convert DXF to G-code and simulate if requested
        print("[MAIN] Calling dxf_to_gcode..."); sys.stdout.flush()
        dxf_to_gcode(args.input_file, args.output_file, 
                     args.feedrate_xy, args.feedrate_z, 
                     args.safe_z, args.cut_z, args.offset_x, args.offset_y, args.start_x, args.start_y, args.end_x, args.end_y)
        print("[MAIN] dxf_to_gcode returned."); sys.stdout.flush()
        
        if args.simulate:
            print("[MAIN] Calling simulate_gcode with Plotly..."); sys.stdout.flush()
            simulate_gcode(args.output_file, offset_x=args.offset_x, offset_y=args.offset_y, start_x=args.start_x, start_y=args.start_y, end_x=args.end_x, end_y=args.end_y)
            print("[NOTE] G-code was generated successfully.")
            print("[NOTE] An interactive HTML visualization has been created. Open 'simulation_plot.html' in your browser.")
    
    except Exception as e:
        print(f"Error in main function: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    main()
