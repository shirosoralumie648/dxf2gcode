import matplotlib
# 使用TkAgg作为交互式后端而不是Agg
matplotlib.use('TkAgg') 
import matplotlib.pyplot as plt
import sys

print(f"Matplotlib version: {matplotlib.__version__}")
print(f"Matplotlibrc file path: {matplotlib.matplotlib_fname()}")
print(f"Default backend being used: {matplotlib.get_backend()}")
sys.stdout.flush()

print("Attempting to create a simple plot and save it...")
sys.stdout.flush()

try:
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3]) # A very simple line
    
    print("Attempting to display the plot instead of saving...")
    sys.stdout.flush()
    
    # 显示图形而不是保存
    print("Calling plt.show()...")
    sys.stdout.flush()
    plt.show()
    
    print("Plot displayed successfully")
    sys.stdout.flush()
    
    # 关闭图形之前先检查是否还存在
    if plt.fignum_exists(fig.number):
        plt.close(fig) # Close the figure
        print("Plot closed.")
        sys.stdout.flush()
    else:
        print("Figure was already closed by plt.show()")
        sys.stdout.flush()

except Exception as e:
    print(f"Python-level error during save: {e}")
    sys.stdout.flush()

print("Test script finished.")
sys.stdout.flush()
