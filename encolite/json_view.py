"""Plain serializable projection of every control supported by the controller."""

FIELDS='''connected noise anc_level dark theme_mode system_dark system_motion system_transparency glass_effect fast_mode fast_launch autostart_enabled autostart_available autostart_error quick_topmost quick_auto_hide quick_idle_seconds accent_mode accent_color system_accent palette status status_error busy connecting cancelling
connection_popup preset wear dual model_name firmware product_picture
can_off can_transparency can_smart can_light can_moderate can_deep can_anc
can_equalizer can_wear can_dual presets preset_name device_names device_index
left_value left_charging left_level right_value right_charging right_level
case_value case_charging case_level battery_layout single_battery_key trace switches noise_options spatial_visible
spatial_mode spatial_options game_options game_type find_visible finding device_info
custom_available custom_names custom_index eq_name eq_minimum eq_maximum bands
multi_available multi_writable multi_devices priority_text model_names model_index'''.split()


class JsonView:
    def __init__(self):
        self.visible=False
        for name in FIELDS:setattr(self,name,None)

    def snapshot(self):
        return {name:getattr(self,name) for name in FIELDS}
