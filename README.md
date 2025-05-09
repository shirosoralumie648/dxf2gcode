# DXF to G-code Converter and Simulator

This project aims to convert 2D geometric entities from DXF files (lines, arcs, circles, polylines, etc.) into G-code suitable for CNC machining or plotting.
It also includes a basic G-code path simulator using Matplotlib.

## Features (Planned)

- Parse DXF files using the `ezdxf` library.
- Support for common DXF entities:
  - LINE
  - ARC
  - CIRCLE
  - LWPOLYLINE
  - POLYLINE
  - SPLINE (approximated as line segments)
  - ELLIPSE (approximated as line segments or polyarcs)
- Generate G-code output (.gcode file).
- Configurable G-code parameters (e.g., feed rates, tool numbers, Z-depths for engraving/cutting).
- Basic 2D G-code path visualization using `matplotlib`.

## Prerequisites

- Python 3.7+

## Installation

1. Clone the repository (or download the files).
2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage (Planned)

```bash
python dxf_to_gcode.py <input_dxf_file> <output_gcode_file> [options]
```

## Development Notes

- **DXF Entity Handling**: The core logic will iterate through entities in the DXF modelspace.
- **Coordinate Systems**: Ensure proper handling of DXF WCS (World Coordinate System) and G-code coordinate systems.
- **Arc Conversion**: DXF arcs need to be converted to G02/G03 commands, which often require start point, end point, and center point or radius.
- **Curve Approximation**: Splines and ellipses will be flattened into polylines (sequences of short line segments) for G-code generation.
- **Simulation**: The simulator will parse the generated G-code and plot X-Y movements.
