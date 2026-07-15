
from faster_whisper import WhisperModel
m = WhisperModel('small', compute_type='int8')
segs, _ = m.transcribe('WhatsApp_Audio_2026-07-15_at_17_07_36_1_.mp3', 
                       'WhatsApp Audio 2026-07-15 at 17.07.35',
                       'WhatsApp Audio 2026-07-15 at 17.07.36',
                       'WhatsApp Audio 2026-07-15 at 17.07.36(2)',
                       'WhatsApp Audio 2026-07-15 at 17.07.37',
                       'WhatsApp Audio 2026-07-15 at 17.07.37(1)',
                       'WhatsApp Audio 2026-07-15 at 17.07.37(2)',
                       'WhatsApp Audio 2026-07-15 at 17.07.37(3)',
                       'WhatsApp Audio 2026-07-15 at 17.07.38',
                       'WhatsApp Audio 2026-07-15 at 17.07.38(1)',
                        'WhatsApp Audio 2026-07-15 at 17.07.38',
                       
                       language='pt')
[print(f'[{s.start:.1f}s] {s.text}') for s in segs]
