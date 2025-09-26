#!/usr/bin/env python3
"""
Haldex DEM Module Monitor
Communicates with 2005 Volvo XC70 Haldex AWD unit via CAN bus
Requires: python-can library and UCAN device with candlelight firmware
"""

import can
import time
import struct
from typing import Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HaldexMonitor:
    def __init__(self, interface='gs_usb', channel='/dev/tty.usbmodem*', bitrate=500000):
        """
        Initialize Haldex monitor

        Args:
            interface: CAN interface type (default: gs_usb for CANtact/UCAN on Mac)
            channel: CAN channel (default: /dev/tty.usbmodem* for USB serial)
            bitrate: CAN bus bitrate (500kbps for Volvo HS CAN)
        """
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self.bus = None
        self.multi_frame_buffer = {}

        # Haldex DEM module configuration
        self.DEM_REQUEST_ID = 0x000FFFFE
        self.DEM_RESPONSE_ID = 0x01204001
        self.DEM_MODULE_ID = 0x1a

        # Sensor request codes
        self.SENSORS = {
            'pump_current': [0xa6, 0x00, 0x05, 0x01],
            'oil_pressure': [0xa6, 0x00, 0x03, 0x01],
            'oil_temperature': [0xa6, 0x00, 0x02, 0x01],
            'wheel_speeds': [0xa6, 0x00, 0x06, 0x01]
        }

    def connect(self):
        """Initialize CAN bus connection"""
        try:
            # Auto-detect USB device if wildcard used
            if '*' in self.channel:
                import glob
                devices = glob.glob(self.channel)
                if not devices:
                    logger.error(f"No USB devices found matching {self.channel}")
                    return False
                self.channel = devices[0]
                logger.info(f"Found USB device: {self.channel}")

            # Try multiple interfaces for candlelight firmware compatibility
            interfaces_to_try = []

            if self.interface == 'gs_usb':
                interfaces_to_try = ['gs_usb', 'slcan', 'serial']
            else:
                interfaces_to_try = [self.interface]

            for interface in interfaces_to_try:
                try:
                    logger.info(f"Trying interface: {interface}")

                    if interface == 'serial':
                        # For serial interface, we need to configure SLCAN mode
                        self.bus = can.interface.Bus(
                            channel=self.channel,
                            interface='slcan',
                            bitrate=self.bitrate
                        )
                    else:
                        self.bus = can.interface.Bus(
                            channel=self.channel,
                            interface=interface,
                            bitrate=self.bitrate
                        )

                    logger.info(f"Connected to CAN bus: {interface} on {self.channel} at {self.bitrate}bps")
                    return True

                except Exception as interface_error:
                    logger.debug(f"Interface {interface} failed: {interface_error}")
                    continue

            # If all interfaces failed
            logger.error("Failed to connect with any interface")
            logger.error("Make sure your CANtact/UCAN device is connected and has candlelight firmware")
            logger.error("You may need to install: pip install pyusb")
            return False

        except Exception as e:
            logger.error(f"Failed to connect to CAN bus: {e}")
            return False

    def disconnect(self):
        """Close CAN bus connection"""
        if self.bus:
            self.bus.shutdown()
            logger.info("Disconnected from CAN bus")

    def send_request(self, sensor_name: str) -> bool:
        """
        Send request message to Haldex DEM module

        Args:
            sensor_name: Name of sensor to request ('pump_current', 'oil_pressure', etc.)

        Returns:
            True if message sent successfully
        """
        if sensor_name not in self.SENSORS:
            logger.error(f"Unknown sensor: {sensor_name}")
            return False

        if not self.bus:
            logger.error("CAN bus not connected")
            return False

        # Build request message
        request_data = self.SENSORS[sensor_name]
        data_length = len(request_data) + 1  # +1 for response count

        # Message format: [length_code, module_id, ...request_data, response_count]
        message_data = [
            0xc8 + data_length,  # Message length (0xc8 + data bytes)
            self.DEM_MODULE_ID,  # DEM module ID (0x1a)
        ] + request_data + [0x01]  # Request data + 1 response expected

        # Pad to 8 bytes
        while len(message_data) < 8:
            message_data.append(0x00)

        # Create CAN message
        msg = can.Message(
            arbitration_id=self.DEM_REQUEST_ID,
            data=message_data,
            is_extended_id=True
        )

        try:
            self.bus.send(msg)
            logger.info(f"Sent request for {sensor_name}: {' '.join(f'{b:02X}' for b in message_data)}")
            return True
        except Exception as e:
            logger.error(f"Failed to send request: {e}")
            return False

    def parse_multi_frame_response(self, msg: can.Message) -> Optional[bytes]:
        """
        Handle multi-frame responses from Haldex module

        Args:
            msg: CAN message received

        Returns:
            Complete message data if frame sequence is complete, None otherwise
        """
        msg_id = msg.arbitration_id
        data = msg.data

        # Check if this is start of multi-frame sequence
        if data[0] & 0x80:  # Frame start bit
            self.multi_frame_buffer[msg_id] = bytearray()
            frame_length = data[0] & 0x0f
            # Copy all data for first frame
            self.multi_frame_buffer[msg_id].extend(data)
            logger.debug(f"Multi-frame start: {' '.join(f'{b:02X}' for b in data)}")
        else:
            # Continuation frame
            if msg_id not in self.multi_frame_buffer:
                logger.warning("Received continuation frame without start frame")
                return None

            # Skip frame header byte and copy data
            frame_data_len = data[0] & 0x0f
            if frame_data_len > 0:
                self.multi_frame_buffer[msg_id].extend(data[1:frame_data_len+1])

            logger.debug(f"Multi-frame continuation: {' '.join(f'{b:02X}' for b in data)}")

        # Check if this is the end frame
        if data[0] & 0x40 == 0:  # Not end frame
            return None

        # Frame sequence complete
        complete_data = bytes(self.multi_frame_buffer[msg_id])
        del self.multi_frame_buffer[msg_id]
        logger.debug(f"Multi-frame complete: {' '.join(f'{b:02X}' for b in complete_data)}")
        return complete_data

    def parse_sensor_response(self, data: bytes, sensor_name: str) -> Dict[str, Any]:
        """
        Parse sensor data from response

        Args:
            data: Complete response data
            sensor_name: Type of sensor requested

        Returns:
            Dictionary with parsed sensor values
        """
        result = {}

        if len(data) < 6:
            logger.warning("Response data too short")
            return result

        if sensor_name == 'pump_current':
            # Extract pump and solenoid currents
            if len(data) >= 9:
                pump_current = struct.unpack('>h', data[5:7])[0]  # Signed 16-bit
                solenoid_current = struct.unpack('>h', data[7:9])[0]  # Signed 16-bit
                result = {
                    'pump_current_raw': pump_current,
                    'solenoid_current_raw': solenoid_current
                }
                logger.info(f"Haldex currents - Pump: {pump_current} ADC, Solenoid: {solenoid_current} ADC")

        elif sensor_name == 'oil_pressure':
            pressure_raw = data[5]
            pressure_bar = pressure_raw * 0.0164
            result = {
                'oil_pressure_raw': pressure_raw,
                'oil_pressure_bar': pressure_bar
            }
            logger.info(f"Haldex oil pressure: {pressure_bar:.2f} bar ({pressure_raw} raw)")

        elif sensor_name == 'oil_temperature':
            temp_raw = struct.unpack('b', data[5:6])[0]  # Signed 8-bit
            result = {
                'oil_temperature_raw': temp_raw,
                'oil_temperature_celsius': temp_raw
            }
            logger.info(f"Haldex oil temperature: {temp_raw}°C")

        elif sensor_name == 'wheel_speeds':
            # Extract all four wheel speeds
            if len(data) >= 14:
                fr_speed_raw = struct.unpack('>H', data[6:8])[0]   # Front right
                fl_speed_raw = struct.unpack('>H', data[8:10])[0]  # Front left
                rr_speed_raw = struct.unpack('>H', data[10:12])[0] # Rear right
                rl_speed_raw = struct.unpack('>H', data[12:14])[0] # Rear left

                fr_speed = fr_speed_raw * 0.0156
                fl_speed = fl_speed_raw * 0.0156
                rr_speed = rr_speed_raw * 0.0156
                rl_speed = rl_speed_raw * 0.0156

                result = {
                    'front_right_speed_kmh': fr_speed,
                    'front_left_speed_kmh': fl_speed,
                    'rear_right_speed_kmh': rr_speed,
                    'rear_left_speed_kmh': rl_speed,
                    'front_right_speed_raw': fr_speed_raw,
                    'front_left_speed_raw': fl_speed_raw,
                    'rear_right_speed_raw': rr_speed_raw,
                    'rear_left_speed_raw': rl_speed_raw
                }
                logger.info(f"Wheel speeds - FR: {fr_speed:.1f}, FL: {fl_speed:.1f}, RR: {rr_speed:.1f}, RL: {rl_speed:.1f} km/h")

        return result

    def listen_for_response(self, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        Listen for DEM module response

        Args:
            timeout: Maximum time to wait for response

        Returns:
            Parsed sensor data or None if timeout
        """
        if not self.bus:
            logger.error("CAN bus not connected")
            return None

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                msg = self.bus.recv(timeout=0.1)
                if msg and msg.arbitration_id == self.DEM_RESPONSE_ID:
                    logger.debug(f"Received response: {' '.join(f'{b:02X}' for b in msg.data)}")

                    # Handle multi-frame response
                    complete_data = self.parse_multi_frame_response(msg)
                    if complete_data:
                        # Determine sensor type from response
                        if len(complete_data) >= 5:
                            op_id = (complete_data[3] << 8) | complete_data[4]

                            if op_id == 0x0005:
                                return self.parse_sensor_response(complete_data, 'pump_current')
                            elif op_id == 0x0003:
                                return self.parse_sensor_response(complete_data, 'oil_pressure')
                            elif op_id == 0x0002:
                                return self.parse_sensor_response(complete_data, 'oil_temperature')
                            elif op_id == 0x0006:
                                return self.parse_sensor_response(complete_data, 'wheel_speeds')

            except can.CanTimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                break

        logger.warning("Timeout waiting for response")
        return None

    def request_sensor(self, sensor_name: str, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        Request sensor data and wait for response

        Args:
            sensor_name: Name of sensor to request
            timeout: Maximum time to wait for response

        Returns:
            Parsed sensor data or None if failed
        """
        if self.send_request(sensor_name):
            return self.listen_for_response(timeout)
        return None

    def keep_alive_mode(self, interval: float = 0.5):
        """
        Continuously send keep-alive requests to prevent module sleep
        Useful for bench testing when module might go to sleep

        Args:
            interval: Time between keep-alive requests (seconds)
        """
        logger.info(f"Starting keep-alive mode (interval: {interval}s)")
        logger.info("This will continuously request oil temperature to keep module awake")
        logger.info("Switch on your bench module now!")

        try:
            while True:
                # Send simple oil temperature request as keep-alive
                if self.send_request('oil_temperature'):
                    # Listen for any response (don't care about parsing)
                    response = self.listen_for_response(timeout=0.3)
                    if response:
                        temp = response.get('oil_temperature_celsius', 'unknown')
                        logger.info(f"Module responding - Temperature: {temp}°C - keeping alive")
                    else:
                        logger.debug("No response (module may be sleeping)")
                else:
                    logger.warning("Failed to send keep-alive request")

                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Keep-alive mode stopped by user")

    def monitor_with_keepalive(self, monitor_interval: float = 2.0, keepalive_interval: float = 0.5, count: int = 0):
        """
        Monitor sensors while sending periodic keep-alive messages

        Args:
            monitor_interval: Time between full sensor readings (seconds)
            keepalive_interval: Time between keep-alive messages (seconds)
            count: Number of readings to take (0 = infinite)
        """
        logger.info(f"Starting monitoring with keep-alive")
        logger.info(f"Monitor interval: {monitor_interval}s, Keep-alive interval: {keepalive_interval}s")

        last_monitor_time = 0
        last_keepalive_time = 0
        readings = 0

        try:
            while count == 0 or readings < count:
                current_time = time.time()

                # Send keep-alive if needed
                if current_time - last_keepalive_time >= keepalive_interval:
                    self.send_request('oil_temperature')  # Quick keep-alive
                    self.listen_for_response(timeout=0.2)  # Quick check
                    last_keepalive_time = current_time

                # Do full monitoring if needed
                if current_time - last_monitor_time >= monitor_interval:
                    print(f"\n--- Reading {readings + 1} ---")

                    # Request each sensor
                    for sensor_name in self.SENSORS.keys():
                        print(f"\nRequesting {sensor_name}...")
                        result = self.request_sensor(sensor_name)
                        if result:
                            for key, value in result.items():
                                print(f"  {key}: {value}")
                        else:
                            print(f"  Failed to get {sensor_name}")

                        time.sleep(0.3)  # Small delay between requests

                    readings += 1
                    last_monitor_time = current_time

                time.sleep(0.1)  # Small sleep to prevent busy loop

        except KeyboardInterrupt:
            logger.info("Monitoring with keep-alive stopped by user")

    def monitor_all_sensors(self, interval: float = 1.0, count: int = 10):
        """
        Monitor all Haldex sensors continuously

        Args:
            interval: Time between sensor requests (seconds)
            count: Number of readings to take (0 = infinite)
        """
        logger.info(f"Starting Haldex monitoring (interval: {interval}s, count: {count})")

        readings = 0
        while count == 0 or readings < count:
            try:
                print(f"\n--- Reading {readings + 1} ---")

                # Request each sensor
                for sensor_name in self.SENSORS.keys():
                    print(f"\nRequesting {sensor_name}...")
                    result = self.request_sensor(sensor_name)
                    if result:
                        for key, value in result.items():
                            print(f"  {key}: {value}")
                    else:
                        print(f"  Failed to get {sensor_name}")

                    time.sleep(0.5)  # Small delay between requests

                readings += 1
                if count == 0 or readings < count:
                    time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error during monitoring: {e}")
                break


def main():
    """Main function to demonstrate Haldex monitoring"""
    import argparse

    parser = argparse.ArgumentParser(description='Monitor Haldex DEM module via CAN bus')
    parser.add_argument('--interface', default='gs_usb', help='CAN interface (default: gs_usb for CANtact/UCAN)')
    parser.add_argument('--channel', default='/dev/tty.usbmodem*', help='CAN channel (default: /dev/tty.usbmodem*)')
    parser.add_argument('--bitrate', type=int, default=500000, help='CAN bitrate (default: 500000)')
    parser.add_argument('--sensor', choices=['pump_current', 'oil_pressure', 'oil_temperature', 'wheel_speeds'],
                       help='Request specific sensor only')
    parser.add_argument('--interval', type=float, default=2.0, help='Monitoring interval in seconds (default: 2.0)')
    parser.add_argument('--count', type=int, default=10, help='Number of readings (0 = infinite, default: 10)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--keep-alive', action='store_true', help='Keep-alive mode for bench testing')
    parser.add_argument('--keep-alive-interval', type=float, default=0.5, help='Keep-alive interval in seconds (default: 0.5)')
    parser.add_argument('--monitor-with-keepalive', action='store_true', help='Monitor with keep-alive messages')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create monitor instance
    monitor = HaldexMonitor(
        interface=args.interface,
        channel=args.channel,
        bitrate=args.bitrate
    )

    # Connect to CAN bus
    if not monitor.connect():
        print("Failed to connect to CAN bus")
        return 1

    try:
        if args.keep_alive:
            # Keep-alive mode for bench testing
            print("Keep-alive mode: Start the script first, then power on your DEM module")
            monitor.keep_alive_mode(args.keep_alive_interval)
        elif args.monitor_with_keepalive:
            # Monitor with keep-alive
            monitor.monitor_with_keepalive(args.interval, args.keep_alive_interval, args.count)
        elif args.sensor:
            # Request single sensor
            print(f"Requesting {args.sensor}...")
            result = monitor.request_sensor(args.sensor)
            if result:
                for key, value in result.items():
                    print(f"{key}: {value}")
            else:
                print("Failed to get sensor data")
        else:
            # Monitor all sensors
            monitor.monitor_all_sensors(args.interval, args.count)

    finally:
        monitor.disconnect()

    return 0


if __name__ == "__main__":
    exit(main())