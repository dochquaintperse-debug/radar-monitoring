from django.db import models

class RadarSensor(models.Model):
    """雷达传感器模型"""
    name = models.CharField(max_length=100, unique=True, verbose_name="传感器ID")
    display_name = models.CharField(max_length=100, verbose_name="显示名称")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    def __str__(self):
        return self.display_name or self.name

class RadarData(models.Model):
    """雷达数据模型"""
    sensor = models.ForeignKey(RadarSensor, on_delete=models.CASCADE, related_name="data", verbose_name="传感器")
    value = models.IntegerField(verbose_name="数值")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="时间戳")

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sensor.name} - {self.value} - {self.timestamp}"

class TrainingResult(models.Model):
    """训练结果模型"""
    sensor = models.ForeignKey(RadarSensor, on_delete=models.CASCADE, related_name="training_results", verbose_name="传感器")
    average_value = models.FloatField(verbose_name="平均值")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sensor.name} - 平均值: {self.average_value}"
