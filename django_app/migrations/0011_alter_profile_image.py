# Generated by Django 5.0.6 on 2024-07-16 21:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_app', '0010_alter_profile_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='image',
            field=models.ImageField(default='profile_images/1.png', upload_to='profile_images'),
        ),
    ]
