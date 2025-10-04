from django.contrib import admin
from .models import RadarSensor, RadarData, TrainingResult

@admin.register(RadarSensor)
class RadarSensorAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'created_at')

@admin.register(RadarData)
class RadarDataAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'value', 'timestamp')
    list_filter = ('sensor',)

@admin.register(TrainingResult)
class TrainingResultAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'average_value', 'created_at')
    list_filter = ('sensor',)