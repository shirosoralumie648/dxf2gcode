import ezdxf

def create_sample_dxf(filename="test_pattern.dxf"):
    doc = ezdxf.new(dxfversion='R2010')  # Create a new DXF document
    msp = doc.modelspace()  # Get the modelspace

    # Add a LINE: (0,0) to (50,50)
    msp.add_line((0, 0), (50, 50))

    # Add an ARC: 
    # Start point implied by previous entity or can be explicit
    # For simplicity here, let's define center, radius, start/end angles
    # Center (75, 50), Radius 25, Start Angle 180 deg, End Angle 0 deg (clockwise arc for G02)
    # ezdxf angles are in degrees, counter-clockwise by default.
    # To make it a continuous path with the line:
    # Line ends at (50,50). Let this be the start of the arc.
    # Arc end point: (100, 0)
    # To form a G02 (clockwise arc), ezdxf needs start_angle > end_angle if we think CCW angles
    # Or, we specify center, start_point, end_point to ezdxf.add_arc_3p later if needed
    # For now, a simple arc: center (75,25), radius 25, from 180 to 0 degrees (draws upper half of circle)
    # This arc will be from (50,25) to (100,25)
    msp.add_arc(
        center=(75, 25),
        radius=25,
        start_angle=180,  # Start angle in degrees
        end_angle=0     # End angle in degrees
    )

    # Add a CIRCLE: center (25, 75), radius 10
    msp.add_circle(center=(25, 75), radius=10)

    # Add an LWPOLYLINE (a lightweight polyline)
    # A rectangle from (10,10) to (40,30)
    points = [(110, 10), (140, 10), (140, 30), (110, 30), (110, 10)]
    msp.add_lwpolyline(points)

    try:
        doc.saveas(filename)
        print(f"Successfully created {filename}")
    except IOError:
        print(f"Error saving {filename}")

if __name__ == '__main__':
    create_sample_dxf()
