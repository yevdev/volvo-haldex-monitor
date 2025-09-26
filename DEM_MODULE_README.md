# DEM Module CAN Bus Messages Documentation

## Sources
https://waal70blog.wordpress.com/2015/12/02/the-can-network-on-a-volvo-part-three-message-interpretation/

## Overview
The DEM module is the Haldex all-wheel drive rear differential unit in Volvo 2004-2014+. This module controls the rear differential coupling and provides sensor data including pump currents, hydraulic oil pressure/temperature, and wheel speeds for the AWD system.
Part of this repo is the CAN bus protocol documentation for the DEM module, but also parsing the response output into a visual dashboard. 

## Module Configuration
- **Module ID**: `0x1a` (26 decimal)
- **CAN ID**: `0x01204001` (Request response ID)
- **CAN Bus**: High Speed (CAN_HS)
- **Frame Type**: MULTIFRAME
- **Default Update Interval**: 250ms

## CAN Bus Protocol Format

### Request Message Format
```
000FFFFE | CD 1A A6 XX XX 01 00 00
          |  |  |  |  |  |
          |  |  |  |  |  '-- Number of responses expected (01)
          |  |  |  '------ Operation ID (sensor specific)
          |  |  '--------- Type of operation (A6 = read data by identifier)
          |  '------------ Module ID (1A = DEM)
          '--------------- Message length (CD = 5 data bytes)
```

### Response Message Format
```
01204001 | CE 1A E6 XX XX YY YY 00
          |  |  |  |  |  |  |
          |  |  |  |  |  '------- Data bytes (sensor values)
          |  |  |  '------ Operation ID (matches request)
          |  |  '--------- Response type (E6 = response by identifier)
          |  '------------ Module ID (1A = DEM)
          '--------------- Message length (CE = 6 data bytes)
```

## Sensor Requests and Responses

### 1. DEM_PUMP_CURRENT (Also returns DEM_SOLENOID_CURRENT)
**Description**: Returns both Haldex hydraulic pump current and solenoid current in one response

**Request**:
```
000FFFFE | CD 1A A6 00 05 01 00 00
```

**Response**:
```
01204001 | Multi-frame response with pump current in bytes[5-6] and solenoid current in bytes[7-8]
```

**Data Processing**:
- Haldex Pump Current: `(int16_t)(256 * bytes[5] + bytes[6])` (raw ADC units)
- Haldex Solenoid Current: `(int16_t)(256 * bytes[7] + bytes[8])` (raw ADC units)

### 2. DEM_OIL_PRESSURE
**Description**: Haldex hydraulic oil pressure sensor

**Request**:
```
000FFFFE | CD 1A A6 00 03 01 00 00
```

**Response**:
```
01204001 | CE 1A E6 00 03 XX 00 00
                         ^^
                    Oil pressure data
```

**Data Processing**:
- Haldex Oil Pressure: `bytes[5] * 0.0164` (bar)

### 3. DEM_OIL_TEMPERATURE
**Description**: Haldex hydraulic oil temperature sensor

**Request**:
```
000FFFFE | CD 1A A6 00 02 01 00 00
```

**Response**:
```
01204001 | CE 1A E6 00 02 XX 00 00
                         ^^
                    Oil temperature data
```

**Data Processing**:
- Haldex Oil Temperature: `(signed char)bytes[5]` (°C)

### 4. DEM_FRONT_LEFT_SPEED (Also returns all wheel speeds)
**Description**: Returns all four wheel speeds in one multi-frame response

**Request**:
```
000FFFFE | CD 1A A6 00 06 01 00 00
```

**Response**:
```
Multi-frame response containing wheel speed data in bytes[6-13]
```

**Data Processing**:
- Front Left Speed: `(uint16_t)(256 * bytes[8] + bytes[9]) * 0.0156` (km/h)
- Front Right Speed: `(uint16_t)(256 * bytes[6] + bytes[7]) * 0.0156` (km/h)
- Rear Left Speed: `(uint16_t)(256 * bytes[12] + bytes[13]) * 0.0156` (km/h)
- Rear Right Speed: `(uint16_t)(256 * bytes[10] + bytes[11]) * 0.0156` (km/h)

## Summary of CAN Messages

| Sensor | Request Message | Response Listens On | Data Location | Units |
|--------|----------------|---------------------|---------------|--------|
| Haldex Pump & Solenoid Current | `000FFFFE CD 1A A6 00 05 01 00 00` | `01204001` | bytes[5-6], bytes[7-8] | Raw ADC |
| Haldex Oil Pressure | `000FFFFE CD 1A A6 00 03 01 00 00` | `01204001` | bytes[5] | bar (×0.0164) |
| Haldex Oil Temperature | `000FFFFE CD 1A A6 00 02 01 00 00` | `01204001` | bytes[5] | °C (signed) |
| All Wheel Speeds | `000FFFFE CD 1A A6 00 06 01 00 00` | `01204001` | bytes[6-13] | km/h (×0.0156) |

## Implementation Notes

1. **Multi-frame Handling**: The DEM module uses multi-frame responses, so you need to handle frame assembly
2. **Shared Responses**: Some sensors return multiple values in one response (pump/solenoid current, all wheel speeds)
3. **Update Intervals**: Default polling interval is 250ms - don't poll faster than needed
4. **Data Types**: Mix of signed/unsigned integers and floats after conversion
5. **Response Filtering**: Filter responses on CAN ID `0x01204001` to get DEM responses

## Example Usage

To get Haldex oil pressure:
1. Send: `000FFFFE CD 1A A6 00 03 01 00 00`
2. Listen for multi-frame response on `01204001`
3. Extract pressure from byte[5] and multiply by 0.0164 for bar units

To get all wheel speeds (AWD system monitoring):
1. Send: `000FFFFE CD 1A A6 00 06 01 00 00`
2. Listen for multi-frame response on `01204001`
3. Extract 4 wheel speeds from bytes[6-13] and multiply by 0.0156 for km/h

To monitor Haldex pump operation:
1. Send: `000FFFFE CD 1A A6 00 05 01 00 00`
2. Listen for multi-frame response on `01204001`
3. Extract pump current from bytes[5-6] and solenoid current from bytes[7-8] (raw ADC values)




## Documentation copy incase reference blog goes down 

The CAN network on a Volvo – part three – request message format
Leave a reply
There are basically two main types of messages: requests and responses. This post will zoom in on request message. And I introduce a new module ID, 000FFFFE. This, in my car, is the generic ID for sending and receiving diagnostic messages, so the ID you will use to query your car on sensor values and other parameters. Very useful, and most likely the ID you will be using most.

Below is a typical request message:

000FFFFE CD 11 A6 01 96 01 00 00
          |  |  |  |  | |
          |  |  |  |  | '--------- Number of responses expected (query only)
          |  |  |  '-------------- Operation ID/Sensor ID (01 96)
          |  |  '----------------- Type of operation
          | '--------------------  Module id in CEM
          '----------------------- Message length (always C8 + data byte length)

The Message Length, not to be confused with the DLC, tells us how many bytes of data are following. CA=2, CB=3, CC=4, CD=5, CE=6, CF=7. In this case, there are 5 bytes of interest following, namely 11, A6, 01, 96, 01. It is Volvo’s way of subsetting the CAN fixed data length of 8 bytes. Yes, they could have used the DLC for this, but at least this simplifies the hardware part for Volvo somewhat, as now the modules can always consume fixed-length CAN-messages on the hardware level, and deal with the variable length in software.

The “Module id in CEM” identifies the module we are making the request to. In this case, 11, it is the ECM. The ECM has most of the operational sensors, and is therefore the most likely module you will query.

The “Type of operation” is A6. As you can see by the below list, this means “read data by identifier”.

The “Operation ID” is split over two bytes, 0196. In this case pointing to sensor 406, which is the DPF temperature sensor.

Then, finally, the 01 stands for the number of responses expected. Here 01, so we only expect one reply to our request. I have not tested what happens if I increment this number, but I imagine there will be a multitude of response messsages. This field is only relevant for request messages of course.

A1 No Operation Performed (keep alive)
A3 Security Access Mode
A5 Read Current Data By Offset
A6 Read Current Data By Identifier
A7 Read Current Data By Address
A8 Set Data Transmission
A9 Stop Data Transmission
AA Dynamically Define Record
AB Read Freeze Frame Data By Offset
AC Read Freeze Frame
AD Read Freeze Frame By DTC
AE Read DTC
AF Clear DTC

B0 Input Output Control By Offset
B1 Input Output Control By Identifier
B2 Control Routine By Offset
B4 Define Read Write ECU data
B8 Write Data Block By Offset
B9 Read Data Block By Offset
BA Write Data Block By Address
BB Read Data Block By Address

The CAN network on a Volvo – part four – response message format
So, in our previous post, we broadcasted a message onto the CAN network, requesting the current value of the DPF temperature sensor:

000FFFFE | CD 11 A6 01 96 01 00 00

We are expecting a response on this, and, lo-and-behold, a response is generated:

01200021 | CE 11 E6 01 96 0C 0D 00

With our newly-found knowledge, it is fairly easy to dissect this:

01200021 is the diagnostic response identifier. Good to know, because we can filter on this ID to only consume response messages, and ignore all the other noise on the CAN network.

CE is indicating an interesting message length of 6 bytes, so 11 E6 01 96 0C 0D, we are discarding the trailing 00.

We asked our question to module 11, and yes, the answer is generated by module 11. So far, so good!

Our request was an A6, so E6 must mean response by identifier.

0196 is that identifier, which nicely corresponds to the identifier we requested.

0C0D is then the hexadecimal representation of that value. In decimal this corresponds to 3085. 3085 degrees? Phew, that is hot and well above the melting point of lots of solids used in my Volvo, yet it is still there.

Some trial-and-error reveals that the temperature is actually represented in decikelvins. As you of course know, the absolute zero of the Kelvin scale is -273.15 degrees Celsius, so if we divide our decimal value by 10 and then “add” the absolute zero, we get the degrees in Celsius:

3085/10 – 273.15 = 35.35, corrected for accuracy is 35.4 degrees Celsius!