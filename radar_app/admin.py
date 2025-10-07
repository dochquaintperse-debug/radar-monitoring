from django.contrib import admin
from .models import RadarSensor, RadarData

@admin.register(RadarSensor)
class RadarSensorAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'created_at')
@admin.register(RadarData)
class RadarDataAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'value', 'timestamp')
    list_filter = ('sensor',)