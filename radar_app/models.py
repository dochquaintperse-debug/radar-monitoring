from django.db import models

class RadarSensor(models.Model):
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.display_name or self.name
class RadarData(models.Model):
    sensor = models.ForeignKey(RadarSensor, on_delete=models.CASCADE)
    value = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-timestamp']
