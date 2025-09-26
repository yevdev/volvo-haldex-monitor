#!/usr/bin/env python3
"""
Haldex DEM Fixed Dashboard
Simple, reliable in-place terminal updates using proper cursor positioning
"""

import sys
import time
import threading
from datetime import datetime
from haldex_gen2_monitor import HaldexMonitor

class FixedDashboard:
    def __init__(self, interface='gs_usb', channel='/dev/tty.usbmodem*', bitrate=500000):
        self.monitor = HaldexMonitor(interface, channel, bitrate)
        self.running = False
        self.data_lock = threading.Lock()

        # Data storage
        self.sensor_data = {
            'oil_temperature_c': None,
            'oil_temperature_f': None,
            'oil_pressure_bar': None,
            'pump_current': None,
            'solenoid_current': None,
            'wheel_speeds': {'fl': None, 'fr': None, 'rl': None, 'rr': None}
        }

        # Status
        self.last_update = None
        self.update_count = 0
        self.errors = 0

    def celsius_to_fahrenheit(self, celsius):
        """Convert Celsius to Fahrenheit"""
        if celsius is not None:
            return (celsius * 9.0 / 5.0) + 32
        return None

    def clear_screen(self):
        """Clear screen and move cursor to top"""
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()

    def hide_cursor(self):
        """Hide terminal cursor"""
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()

    def show_cursor(self):
        """Show terminal cursor"""
        sys.stdout.write('\033[?25h')
        sys.stdout.flush()

    def collect_sensor_data(self):
        """Background thread to collect sensor data"""
        while self.running:
            try:
                updated = False

                # Oil Temperature (most reliable sensor for keep-alive)
                result = self.monitor.request_sensor('oil_temperature', timeout=1.0)
                if result:
                    with self.data_lock:
                        temp_c = result.get('oil_temperature_celsius')
                        self.sensor_data['oil_temperature_c'] = temp_c
                        self.sensor_data['oil_temperature_f'] = self.celsius_to_fahrenheit(temp_c)
                        updated = True

                # Oil Pressure
                result = self.monitor.request_sensor('oil_pressure', timeout=1.0)
                if result:
                    with self.data_lock:
                        self.sensor_data['oil_pressure_bar'] = result.get('oil_pressure_bar')
                        updated = True

                # Pump and Solenoid Current
                result = self.monitor.request_sensor('pump_current', timeout=1.0)
                if result:
                    with self.data_lock:
                        self.sensor_data['pump_current'] = result.get('pump_current_raw')
                        self.sensor_data['solenoid_current'] = result.get('solenoid_current_raw')
                        updated = True

                # Wheel Speeds
                result = self.monitor.request_sensor('wheel_speeds', timeout=1.0)
                if result:
                    with self.data_lock:
                        speeds = self.sensor_data['wheel_speeds']
                        speeds['fl'] = result.get('front_left_speed_kmh')
                        speeds['fr'] = result.get('front_right_speed_kmh')
                        speeds['rl'] = result.get('rear_left_speed_kmh')
                        speeds['rr'] = result.get('rear_right_speed_kmh')
                        updated = True

                with self.data_lock:
                    if updated:
                        self.last_update = datetime.now()
                        self.update_count += 1
                    else:
                        self.errors += 1

                time.sleep(1.0)  # Collect data every second

            except Exception as e:
                with self.data_lock:
                    self.errors += 1
                time.sleep(2.0)

    def render_dashboard(self):
        """Render the dashboard with proper screen control"""
        update_interval = 1.0  # Update display every second

        while self.running:
            try:
                # Move cursor to home position (top-left)
                sys.stdout.write('\033[H')

                with self.data_lock:
                    current_data = self.sensor_data.copy()
                    last_update = self.last_update
                    update_count = self.update_count
                    errors = self.errors

                # Build the entire screen content as a single string
                output = []

                # Title
                output.append("🔧 HALDEX DEM MODULE - LIVE MONITOR 🔧")
                output.append("=" * 60)

                # Status
                if last_update:
                    status = f"Last Update: {last_update.strftime('%H:%M:%S')} | Updates: {update_count} | Errors: {errors}"
                else:
                    status = "Waiting for data..."
                output.append(f"Status: {status}")
                output.append("")

                # Oil Temperature
                output.append("🌡️  OIL TEMPERATURE")
                temp_c = current_data['oil_temperature_c']
                temp_f = current_data['oil_temperature_f']

                if temp_c is not None and temp_f is not None:
                    output.append(f"   {temp_c:.1f}°C ({temp_f:.1f}°F)")

                    # Temperature status with bar
                    if temp_c < 0:
                        temp_status = "🥶 Very Cold"
                        bar_fill = max(1, int(20 * (temp_c + 10) / 130))
                    elif temp_c < 20:
                        temp_status = "❄️  Cold"
                        bar_fill = max(1, int(20 * temp_c / 130))
                    elif temp_c < 50:
                        temp_status = "✅ Normal"
                        bar_fill = max(1, int(20 * temp_c / 130))
                    elif temp_c < 80:
                        temp_status = "🔥 Warm"
                        bar_fill = max(1, int(20 * temp_c / 130))
                    else:
                        temp_status = "🚨 Hot"
                        bar_fill = 20

                    temp_bar = "█" * bar_fill + "░" * (20 - bar_fill)
                    output.append(f"   Status: {temp_status}")
                    output.append(f"   [{temp_bar}] (-10°C to 120°C)")
                else:
                    output.append("   No Data")
                    output.append("   Status: Unknown")
                    output.append("   [░░░░░░░░░░░░░░░░░░░░] (-10°C to 120°C)")

                output.append("")

                # Oil Pressure
                output.append("💧 OIL PRESSURE")
                pressure = current_data['oil_pressure_bar']
                if pressure is not None:
                    psi = pressure * 14.504
                    output.append(f"   {pressure:.2f} bar ({psi:.1f} psi)")

                    # Pressure status with bar
                    if pressure < 0.5:
                        pressure_status = "🚨 Very Low"
                    elif pressure < 1.0:
                        pressure_status = "⚠️  Low"
                    elif pressure < 5.0:
                        pressure_status = "✅ Normal"
                    else:
                        pressure_status = "🔥 High"

                    bar_fill = max(1, min(20, int(20 * pressure / 10)))
                    pressure_bar = "█" * bar_fill + "░" * (20 - bar_fill)

                    output.append(f"   Status: {pressure_status}")
                    output.append(f"   [{pressure_bar}] (0-10 bar)")
                else:
                    output.append("   No Data")
                    output.append("   Status: Unknown")
                    output.append("   [░░░░░░░░░░░░░░░░░░░░] (0-10 bar)")

                output.append("")

                # Currents
                output.append("⚡ ELECTRICAL CURRENTS")
                pump = current_data['pump_current']
                solenoid = current_data['solenoid_current']

                if pump is not None and solenoid is not None:
                    pump_status = "🔋 Active" if pump > 100 else "💤 Inactive"
                    solenoid_status = "🔋 Active" if solenoid > 100 else "💤 Inactive"

                    output.append(f"   Pump:     {pump:>6} ADC ({pump_status})")
                    output.append(f"   Solenoid: {solenoid:>6} ADC ({solenoid_status})")
                else:
                    output.append("   Pump:     No Data")
                    output.append("   Solenoid: No Data")

                output.append("")

                # Wheel Speeds
                output.append("🚗 WHEEL SPEEDS")
                speeds = current_data['wheel_speeds']
                if all(v is not None for v in speeds.values()):
                    output.append(f"   FL: {speeds['fl']:>5.1f} km/h  FR: {speeds['fr']:>5.1f} km/h")
                    output.append(f"   RL: {speeds['rl']:>5.1f} km/h  RR: {speeds['rr']:>5.1f} km/h")

                    # Speed difference analysis
                    max_speed = max(speeds.values())
                    min_speed = min(speeds.values())
                    speed_diff = max_speed - min_speed

                    if speed_diff > 5:
                        diff_status = "⚠️  High difference"
                    elif speed_diff > 2:
                        diff_status = "⚖️  Minor difference"
                    else:
                        diff_status = "✅ Balanced"

                    output.append(f"   Status: {diff_status} (Δ{speed_diff:.1f})")
                else:
                    output.append("   FL: ----- km/h  FR: ----- km/h")
                    output.append("   RL: ----- km/h  RR: ----- km/h")
                    output.append("   Status: No Data")

                output.append("")

                # Footer
                output.append("=" * 60)
                output.append("Press Ctrl+C to quit | Updating every 1 second")

                # Add extra blank lines to clear any leftover content
                output.extend([""] * 5)

                # Write entire screen content at once
                screen_content = "\n".join(output)
                sys.stdout.write(screen_content)
                sys.stdout.flush()

                time.sleep(update_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                # Handle any rendering errors gracefully
                time.sleep(1)

    def run(self):
        """Run the fixed dashboard"""
        print("Starting Haldex Fixed Dashboard...")
        print("Connecting to CAN bus...")

        if not self.monitor.connect():
            print("Failed to connect to CAN bus")
            return 1

        print("Connected! Starting dashboard in 2 seconds...")
        time.sleep(2)

        # Clear screen once and hide cursor
        self.clear_screen()
        self.hide_cursor()

        self.running = True

        try:
            # Start data collection thread
            data_thread = threading.Thread(target=self.collect_sensor_data, daemon=True)
            data_thread.start()

            # Run the display
            self.render_dashboard()

        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            self.show_cursor()
            self.monitor.disconnect()
            # Clear screen and show cursor
            self.clear_screen()
            print("Dashboard stopped.\n")

        return 0

def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Haldex DEM Fixed Dashboard')
    parser.add_argument('--interface', default='gs_usb', help='CAN interface (default: gs_usb)')
    parser.add_argument('--channel', default='/dev/tty.usbmodem*', help='CAN channel (default: /dev/tty.usbmodem*)')
    parser.add_argument('--bitrate', type=int, default=500000, help='CAN bitrate (default: 500000)')

    args = parser.parse_args()

    dashboard = FixedDashboard(
        interface=args.interface,
        channel=args.channel,
        bitrate=args.bitrate
    )

    return dashboard.run()

if __name__ == "__main__":
    exit(main())