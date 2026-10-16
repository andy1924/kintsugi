"""Combine semantic vision assessment with bounded, deterministic repair geometry."""
import io
from PIL import Image
from . import config
from .imaging import segment
from .vision import assess_damage, VisionError


def analyze_damage(data, settings):
    if config.analysis_provider() == 'local':
        return segment(data, settings)
    assessment = assess_damage(data, settings)
    # Optional user adjustments always win over model suggestions.
    chosen_box = settings.get('box')
    if chosen_box is None:
        chosen_box = assessment.box.coordinates() if assessment.damage_found else [.15, .15, .85, .85]
        chosen_box = [max(.005, min(.995, v)) for v in chosen_box]
    effective = {**settings, 'box': chosen_box, 'fabric': settings.get('fabric') or assessment.fabric}
    with Image.open(io.BytesIO(data)) as image:
        x0,y0,x1,y1 = chosen_box
        pixel_width = int(x1*image.width)-max(1,int(x0*image.width))
        pixel_height = int(y1*image.height)-max(1,int(y0*image.height))
    if min(pixel_width, pixel_height) < 5:
        raise VisionError('The detected damage is too small in this photo. Upload a closer photo or adjust the damage area.')
    if settings.get('width_mm') and pixel_height/pixel_width*settings['width_mm'] > 400:
        raise VisionError('This repair is taller than 400 mm at the entered width. Adjust the area or split it into smaller repairs.')
    result = segment(data, effective)
    result.update({
        'provider': 'openai', 'vision_model': config.OPENAI_VISION_MODEL,
        'engine': 'OpenAI vision + '+result['engine'],
        'assessment': assessment.summary, 'damage_type': assessment.damage_type,
        'severity': assessment.severity, 'confidence': assessment.confidence,
        'damage_found': assessment.damage_found, 'repair_advice': assessment.repair_advice,
        'recommended_style': assessment.recommended_style,
        'detection': 'user_adjusted' if settings.get('box') else ('suggested' if assessment.damage_found else 'uncertain'),
        'requires_manual_area': not assessment.damage_found and settings.get('box') is None,
    })
    result['warnings'].extend(assessment.warnings)
    if assessment.confidence == 'low':
        result['warnings'].append('The AI assessment is uncertain. Review the damage closely or ask a maker before proceeding.')
    if not assessment.damage_found:
        result['warnings'].append('No clear damage was identified. Adjust the area or upload a clearer close-up before creating a pattern.')
    return result
