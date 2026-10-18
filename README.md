# Mini EMS - Home Assistant Integration
### Tích hợp đầy đủ cho Donnergy / Absaar Inverter (mini-ems.com)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/duylamstore/mini_ems_ha.svg)](https://github.com/duylamstore/mini_ems_ha/releases)
[![License](https://img.shields.io/github/license/duylamstore/mini_ems_ha.svg)](LICENSE)

Tích hợp này kết nối **Home Assistant** với đám mây **mini-ems.com** để lấy toàn bộ dữ liệu biến tần Donnergy/Absaar theo thời gian thực — nhiều hơn gấp 3-4 lần so với integration Absaar mặc định.

---

## ✨ Tính năng

- 🌞 **40+ Sensors**: PV1/PV2, pin, lưới, tải, biến tần, sản lượng, thu nhập...
- 🔔 **7 Binary Sensors**: online, sạc/xả pin, mua/bán điện, cập nhật firmware
- 🎛️ **Điều khiển từ xa**: chế độ hoạt động, chế độ sạc, SOC min/max, bán điện, sạc cưỡng bức
- 🔄 **Tự động refresh**: mặc định 30 giây, có thể chỉnh từ 10 giây
- 🔑 **Tự động re-login**: token hết hạn tự gia hạn
- 🇻🇳 Giao diện **tiếng Việt**

---

## 📦 Cài đặt qua HACS

### Bước 1: Thêm Custom Repository
1. Mở HACS → **Integrations** → ⋮ → **Custom repositories**
2. Thêm URL: `https://github.com/duylamstore/mini_ems_ha`
3. Category: **Integration**

### Bước 2: Cài đặt
1. Tìm **"Mini EMS"** trong HACS
2. Nhấn **Download**
3. **Restart Home Assistant**

### Bước 3: Thêm Integration
1. **Settings → Devices & Services → Add Integration**
2. Tìm **"Mini EMS"**
3. Nhập thông tin tài khoản mini-ems.com
4. Chọn biến tần muốn theo dõi

---

## 🔌 Cài đặt thủ công

```bash
# SSH vào Home Assistant
mkdir -p /config/custom_components
cd /tmp
wget https://github.com/duylamstore/mini_ems_ha/archive/refs/heads/main.zip
unzip main.zip
cp -r mini_ems_ha-main/custom_components/mini_ems /config/custom_components/
# Restart HA
```

---

## 📊 Danh sách Sensors

### Overview (từ cloud)
| Sensor | Mô tả | Đơn vị |
|--------|-------|--------|
| `current_power` | Công suất hiện tại | W |
| `daily_power_generation` | Sản lượng hôm nay | kWh |
| `total_power_generation` | Tổng sản lượng | kWh |
| `income_of_the_day` | Thu nhập hôm nay | VND |
| `cumulative_income` | Tổng thu nhập | VND |
| `emission_reduction_co2` | Giảm phát thải CO₂ | kg |

### PV Mặt Trời
| Sensor | Mô tả | Đơn vị |
|--------|-------|--------|
| `pv1_power` / `pv2_power` | Công suất PV1/PV2 | W |
| `pv1_voltage` / `pv2_voltage` | Điện áp PV1/PV2 | V |
| `pv1_current` / `pv2_current` | Dòng điện PV1/PV2 | A |
| `pv_total_power` | Tổng công suất PV | W |

### Pin Lưu Trữ
| Sensor | Mô tả | Đơn vị |
|--------|-------|--------|
| `battery_soc` | Mức sạc (SOC) | % |
| `battery_power` | Công suất pin (+sạc/-xả) | W |
| `battery_voltage` | Điện áp pin | V |
| `battery_current` | Dòng điện pin | A |
| `battery_temperature` | Nhiệt độ pin | °C |
| `charger_energy_today` | Điện sạc hôm nay | kWh |
| `dis_charger_energy_today` | Điện xả hôm nay | kWh |

### AC / Lưới Điện
| Sensor | Mô tả | Đơn vị |
|--------|-------|--------|
| `ac_voltage` | Điện áp AC lưới | V |
| `ac_current` | Dòng điện AC | A |
| `ac_power` | Công suất AC | W |
| `ac_frequency` | Tần số lưới | Hz |
| `grid_energy_in_today` | Điện mua hôm nay | kWh |
| `grid_energy_out_today` | Điện bán hôm nay | kWh |

### Biến Tần
| Sensor | Mô tả | Đơn vị |
|--------|-------|--------|
| `inverter_temperature` | Nhiệt độ biến tần | °C |
| `operation_hours` | Giờ hoạt động | h |
| `firmware_version` | Phiên bản firmware | - |
| `system_status` | Trạng thái hệ thống | - |
| `self_consumption_ratio` | Tỷ lệ tự tiêu thụ | % |

### Tải Tiêu Thụ
| Sensor | Mô tả | Đơn vị |
|--------|-------|--------|
| `load_power` | Công suất tải | W |
| `load_voltage` | Điện áp tải | V |
| `load_current` | Dòng điện tải | A |

---

## 🎛️ Điều Khiển

| Entity | Loại | Chức năng |
|--------|------|-----------|
| `work_mode` | Select | Solar/Battery/Grid First, Self-Consumption |
| `charge_mode` | Select | Auto / Solar Only / Solar+Grid |
| `battery_min_soc` | Number | SOC tối thiểu (5–95%) |
| `battery_max_soc` | Number | SOC tối đa (10–100%) |
| `grid_export` | Switch | Cho phép/cấm bán điện lên lưới |
| `force_charge` | Switch | Buộc sạc pin từ lưới điện |

---

## 🔑 API Endpoints

Integration sử dụng API của `https://mini-ems.com:8081` (reverse engineered):

```
POST /dn/login                              → JWT auth
POST /dn/power/inverter/overviewApp         → Overview stats
POST /dn/system/data/list                   → Real-time sensor data
POST /dn/power/inverterData/stationElectricity → Daily kWh breakdown
POST /dn/send/instructions/sendIn           → Remote control
```

---

## ⚡ Tương thích

| Thiết bị | Hỗ trợ |
|----------|--------|
| Donnergy Hybrid Inverter | ✅ |
| Absaar Inverter | ✅ |
| Bất kỳ inverter nào trên mini-ems.com | ✅ |

---

## 📋 Changelog

### v1.0.0 (2026-10-18)
- 🎉 Release đầu tiên
- 40+ sensors real-time
- 7 binary sensors
- Điều khiển từ xa: work mode, charge mode, SOC limits
- Config flow UI với chọn biến tần
- Tự động re-login khi token hết hạn
- Hỗ trợ tiếng Việt

---

## 🤝 Đóng góp

Pull requests are welcome! Mọi thiết bị dùng mini-ems.com đều được hỗ trợ.

---

## 📄 License

MIT License - Xem [LICENSE](LICENSE)
