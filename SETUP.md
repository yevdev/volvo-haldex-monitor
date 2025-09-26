# Haldex Monitor Setup Guide

## Hardware Requirements
- UCAN/CANtact device flashed with candlelight firmware
- 2005 Volvo XC70 with Haldex AWD system
- OBD-II cable or direct CAN bus connection
- USB cable to connect device to Mac

## Software Requirements
- Python 3.7+
- python-can library

## Installation

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set up USB device (Mac):**
```bash
# Check that your CANtact/UCAN device is detected
ls /dev/tty.usbmodem*

# The script will auto-detect the device
```

3. **For other platforms:**
   - **Linux**: Use `--interface socketcan --channel can0`
   - **Windows**: Use `--interface pcan` or appropriate interface

## Usage

### Basic Usage
```bash
# Monitor all Haldex sensors (10 readings, 2-second intervals)
python haldex_monitor.py

# Monitor specific sensor only
python haldex_monitor.py --sensor oil_pressure

# Continuous monitoring
python haldex_monitor.py --count 0 --interval 1.0

# Debug mode
python haldex_monitor.py --debug
```

### Bench Testing Mode (Direct DEM Module Connection)
```bash
# Keep-alive mode: Start script first, then power on DEM module
python haldex_monitor.py --keep-alive

# Keep-alive with faster interval (0.2 seconds)
python haldex_monitor.py --keep-alive --keep-alive-interval 0.2

# Monitor with keep-alive (prevents module sleep during testing)
python haldex_monitor.py --monitor-with-keepalive --count 0
```

### Real-Time Dashboards
```bash
# Advanced dashboard with ASCII graphs (requires curses support)
python haldex_dashboard.py

# Simple dashboard with clear screen updates
python haldex_simple_dashboard.py

# Dashboard with specific interface
python haldex_dashboard.py --interface slcan --channel /dev/tty.usbmodem123456
```

### Command Line Options
```
--interface           CAN interface type (default: gs_usb for Mac)
--channel             USB device path (default: /dev/tty.usbmodem*)
--bitrate             CAN bitrate (default: 500000)
--sensor              Request specific sensor only
--interval            Monitoring interval in seconds (default: 2.0)
--count               Number of readings (0 = infinite, default: 10)
--debug               Enable debug logging
--keep-alive          Keep-alive mode for bench testing
--keep-alive-interval Keep-alive interval in seconds (default: 0.5)
--monitor-with-keepalive Monitor with periodic keep-alive messages
```

### Available Sensors
- `pump_current` - Haldex pump and solenoid currents
- `oil_pressure` - Hydraulic oil pressure
- `oil_temperature` - Hydraulic oil temperature
- `wheel_speeds` - All four wheel speeds

## Example Output

### Basic Monitor Output
```
--- Reading 1 ---

Requesting pump_current...
Haldex currents - Pump: 1234 ADC, Solenoid: 567 ADC
  pump_current_raw: 1234
  solenoid_current_raw: 567

Requesting oil_temperature...
Haldex oil temperature: 26°C
  oil_temperature_raw: 26
  oil_temperature_celsius: 26
```

### Dashboard Output
```
🔧 HALDEX DEM MODULE - REAL-TIME DASHBOARD 🔧
===============================================================================

Status: Last Update: 17:59:51 | Updates: 25 | Errors: 0

🌡️  OIL TEMPERATURE
--------------------------------------------------
Current: 26.0°C (78.8°F)
Status: ✅ Normal
    ████████████████████████████████████████████████
    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
    -10°C                                        120°C

💧 OIL PRESSURE
--------------------------------------------------
Current: 0.16 bar (2.3 psi)
Status: 🚨 Very Low

⚡ ELECTRICAL CURRENTS
--------------------------------------------------
Pump Current:         0 ADC units
Solenoid Current:     0 ADC units
Pump Status:      💤 Inactive
Solenoid Status:  💤 Inactive

🚗 WHEEL SPEEDS
--------------------------------------------------
Front Left:    0.0 km/h (  0.0 mph)
Front Right:   0.0 km/h (  0.0 mph)
Rear Left:     0.0 km/h (  0.0 mph)
Rear Right:    0.0 km/h (  0.0 mph)
Status: ✅ Wheel speeds balanced
```

## Troubleshooting

### Connection Issues
- Verify USB device is detected: `ls /dev/tty.usbmodem*`
- Check bitrate matches vehicle (500kbps for Volvo HS CAN)
- Ensure proper CAN bus termination
- Verify OBD-II pins 6 (CAN-H) and 14 (CAN-L) connections
- Try unplugging/reconnecting USB device if connection fails

### No Response from Module
- **Vehicle**: Engine should be running or ignition on
- **Bench setup**: Module should have 12V power applied
- Verify you're connected to the high-speed CAN bus
- Try keep-alive mode for bench testing
- Some responses may require vehicle to be moving
- Check debug output for sent/received messages

### Multi-frame Issues
- Increase timeout if responses are slow
- Enable debug mode to see frame assembly
- Check for CAN bus errors or interference

## CAN Bus Pinout (OBD-II)
- Pin 6: CAN-H (High Speed CAN)
- Pin 14: CAN-L (High Speed CAN)
- Pin 4: Chassis Ground
- Pin 16: Battery +12V

## Bench Testing Workflow

For direct DEM module testing with switchable 12V:

1. **Wire connections:**
   - Connect UCAN CAN-H to DEM CAN-H
   - Connect UCAN CAN-L to DEM CAN-L
   - Connect UCAN ground to DEM ground
   - Wire 12V supply to DEM power (switchable)

2. **Start monitoring:**
   ```bash
   python haldex_monitor.py --keep-alive --debug
   ```

3. **Power on module:**
   - Switch on 12V to DEM module
   - Watch for "Module responding - Temperature: XX°C - keeping alive" messages
   - Module should stay awake due to temperature requests

4. **Switch to full monitoring:**
   - Stop keep-alive mode (Ctrl+C)
   - Start full monitoring:
   ```bash
   python haldex_monitor.py --monitor-with-keepalive --count 0
   ```

## Safety Notes
- **Never** disconnect CAN while engine is running
- Use proper ESD protection when handling electronics
- Vehicle should be parked safely during testing
- Monitor for any fault codes after testing
- **Bench testing**: Ensure proper grounding and 12V supply regulation