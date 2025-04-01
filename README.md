# AQI Pico

MicroPython app for showing AQI (Air Quality Index) and current temperature. Data is fetched from https://api.waqi.info for the current IP address.

### Image

![aqi_pico](https://github.com/user-attachments/assets/0794848d-66a6-4367-8202-140e3634b63c)

### Hardware

* [Raspberry Pico 2 W](https://www.raspberrypi.com/products/raspberry-pi-pico-2/)
* [Waveshare RGB LED Panel 16x10](https://www.waveshare.com/wiki/Pico-RGB-LED)

### Features

* Fetching both AQI and current temperature (in Celsius)
* Displaying values using custom glyphs on a 16x10 NeoPixel panel
* Logging to console
* Dumping exceptions to Pico's internal storage
* Switching display off for the desired time frame

### Configuration

* `secrets.py` for WiFi credentials and waqi.info token
* `config.py` for off time and time zone offset, and for wi-fi country selection
