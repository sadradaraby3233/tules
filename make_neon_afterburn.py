#!/usr/bin/env python3
"""Procedurally synthesize NEON AFTERBURN, an original 2-minute club track."""
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io.wavfile import write

SR = 44100
BPM = 128
BEAT = 60.0 / BPM
BAR = 4 * BEAT
BARS = 64
DURATION = BARS * BAR
TAIL = 2.5
N = int((DURATION + TAIL) * SR)
rng = np.random.default_rng(81473)

# Separate buses make the kick-triggered pumping feel intentional, not destructive.
drums = np.zeros((N, 2), np.float32)
music = np.zeros((N, 2), np.float32)
fx = np.zeros((N, 2), np.float32)

def at(bar, beat=0.0):
    return int((bar * BAR + beat * BEAT) * SR)

def put(bus, start, signal, pan=0.0, gain=1.0):
    i = max(0, int(start))
    if i >= N: return
    x = np.asarray(signal, dtype=np.float32)
    end = min(N, i + len(x))
    if end <= i: return
    # Constant-power panning; centered sounds retain their level.
    l = np.cos((pan + 1.0) * np.pi / 4.0)
    r = np.sin((pan + 1.0) * np.pi / 4.0)
    bus[i:end, 0] += x[:end-i] * (gain * l)
    bus[i:end, 1] += x[:end-i] * (gain * r)

def env_exp(length, attack=0.004, decay=0.12, sustain=0.0, release=None):
    t = np.arange(length, dtype=np.float32) / SR
    a = np.minimum(1.0, t / max(attack, 1e-5))
    d = np.exp(-np.maximum(0, t-attack) / max(decay, 1e-4))
    e = a * d
    if release is not None:
        e *= np.minimum(1.0, np.maximum(0.0, (length/SR-t)/release))
    return e.astype(np.float32)

def lowpass(x, cutoff, order=3):
    cutoff = float(np.clip(cutoff, 35, SR*0.46))
    return sosfilt(butter(order, cutoff, fs=SR, output='sos'), x).astype(np.float32)

def bandpass(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype='bandpass', fs=SR, output='sos'), x).astype(np.float32)

def softclip(x, drive=1.5):
    return np.tanh(x * drive).astype(np.float32)

# Punchy synthesized kick: falling sine pitch, short beater tick, and a restrained low tail.
def kick():
    length = int(.48*SR)
    t = np.arange(length, dtype=np.float32)/SR
    phase = 2*np.pi*(47*t + 74*.055*(1-np.exp(-t/.018)))
    body = np.sin(phase) * np.exp(-t/.205)
    click = np.sin(2*np.pi*1850*t) * np.exp(-t/.006) * .18
    low = np.sin(2*np.pi*48*t) * np.exp(-t/.33) * .13
    return softclip((body + click + low)*1.55, 1.3)

KICK = kick()

def clap():
    length=int(.23*SR)
    t=np.arange(length,dtype=np.float32)/SR
    noise=rng.standard_normal(length).astype(np.float32)
    snap=bandpass(noise, 850, 9000)
    # Three tight bursts give the clap a hand-built, layered character.
    gate=np.zeros(length,np.float32)
    for shift,amp in [(0,.8),(.012,.55),(.027,.3)]:
        j=int(shift*SR)
        gate[j:]+=amp*np.exp(-np.arange(length-j,dtype=np.float32)/(SR*.045))
    tone=np.sin(2*np.pi*(190-95*t)*t)*np.exp(-t/.075)*.12
    return softclip(snap*gate*.34+tone, 1.1)

CLAP=clap()

def hat(open_hat=False):
    length=int((.19 if open_hat else .052)*SR)
    t=np.arange(length,dtype=np.float32)/SR
    white=rng.standard_normal(length).astype(np.float32)
    metallic=np.zeros(length,np.float32)
    # Inharmonic metallic partials make the hat more than a noise burst.
    for f,a in [(5230,.32),(6840,.25),(8170,.20),(9730,.13)]:
        metallic += a*np.sin(2*np.pi*f*t + rng.uniform(0,6.28))
    breath=bandpass(white, 6500 if not open_hat else 4800, 15000)*(.13 if not open_hat else .11)
    decay=.105 if open_hat else .021
    return softclip((metallic+breath)*np.exp(-t/decay), 1.2)

CLOSED=hat(False); OPEN=hat(True)

def bass_note(freq, dur, cutoff=2200, accent=1.0, kind='acid'):
    length=max(16,int(dur*SR))
    t=np.arange(length,dtype=np.float32)/SR
    # Slight oscillator drift plus saw/pulse blend for a warm, harmonically rich 303-ish source.
    phase=(freq*t + .0012*np.sin(2*np.pi*4.1*t))*2*np.pi
    saw=2*(np.mod(phase/(2*np.pi),1.0)) - 1
    pulse=np.where(np.sin(phase) >= 0, 1.0, -1.0).astype(np.float32)
    raw=.74*saw+.26*pulse
    # A stepped envelope sweep is intentionally audible as the cutoff opens and closes per note.
    out=np.empty_like(raw)
    state=None
    steps=7
    for k in range(steps):
        lo=k*length//steps; hi=(k+1)*length//steps
        frac=(lo+hi)/(2*length)
        fc=130 + (cutoff-130)*np.exp(-frac*3.0)
        sos=butter(3, float(np.clip(fc,100,8500)), fs=SR, output='sos')
        if state is None:
            out[lo:hi], state=sosfilt(sos,raw[lo:hi],zi=np.zeros((len(sos),2),np.float32))
        else:
            out[lo:hi], state=sosfilt(sos,raw[lo:hi],zi=state)
    e=env_exp(length, attack=.003, decay=.19, release=.035)
    # Accent crunch and resonant-looking upper harmonics, kept on a controlled low end.
    return softclip(out*e*accent*1.9, 1.8)

def sub_note(freq, dur):
    length=int(dur*SR)
    t=np.arange(length,dtype=np.float32)/SR
    fundamental=np.sin(2*np.pi*freq*t)
    second=.17*np.sin(2*np.pi*freq*2.002*t)
    return softclip((fundamental+second)*env_exp(length,.008,.24,.0,.035),1.25)

def lead_note(freq, dur, bright=1.0):
    length=max(16,int(dur*SR)); t=np.arange(length,dtype=np.float32)/SR
    phase=2*np.pi*freq*t
    # Detuned saw pair plus a glassy triangle partial; chorus emerges from the beating.
    raw=.50*(2*np.mod((freq*.997)*t,1)-1)+.40*(2*np.mod((freq*1.004)*t+.18,1)-1)
    raw += .22*(2/np.pi)*np.arcsin(np.sin(phase*2))
    raw=lowpass(raw.astype(np.float32), 1900+bright*3300, 2)
    e=(1-np.exp(-t/.008))*np.exp(-t/(dur*.72))
    return softclip(raw*e,1.3)

def chord(freqs, dur, brightness=1.0):
    length=int(dur*SR); t=np.arange(length,dtype=np.float32)/SR
    out=np.zeros(length,np.float32)
    for k,f in enumerate(freqs):
        # Detuned supersaw-ish chord, with enough high partials to feel synthetic and lush.
        p=t*f
        voice=.42*(2*np.mod(p,1)-1)+.32*(2*np.mod(p*1.006+.2,1)-1)
        voice += .19*np.sin(2*np.pi*f*2.01*t)+.09*np.sin(2*np.pi*f*3*t)
        out += voice/(len(freqs)**.65)
    out=lowpass(out, 650+brightness*1900, 2)
    fade=min(.2,dur*.24)
    e=np.minimum(1,t/.03)*np.minimum(1,np.maximum(0,(dur-t)/fade))
    return softclip(out*e,1.15)

# Four-bar minor-key progression: Dm, Bb, F, C. Midrange chord voicings leave room for bass/kick.
roots=[(38,[50,53,57,62]),(34,[46,50,53,58]),(29,[48,53,57,60]),(36,[48,52,55,60])]
# Lead motif: a rising, memorable D-minor call/response with a high resolve.
melody=[(0,74,.28),(0.75,77,.25),(1.5,81,.33),(2.25,84,.30),(3,81,.25),(3.5,79,.23),(4,77,.40),(5,74,.28),(6,72,.28),(7,69,.44)]

def section(bar):
    if bar<8:return 'intro'
    if bar<16:return 'build'
    if bar<32:return 'drop'
    if bar<40:return 'break'
    if bar<56:return 'drop2'
    return 'outro'

for b in range(BARS):
    sec=section(b)
    chord_idx=(b//4)%4
    root_midi, voicing=roots[chord_idx]
    root=440*2**((root_midi-69)/12)
    # Kick comes in after the intro, ducks out briefly for the breakdown, then slams back.
    kick_on = (b>=4 and not (32<=b<36) and b<63)
    if kick_on:
        for beat in range(4):
            put(drums, at(b,beat), KICK, 0, .91 if sec!='drop2' else .98)
    # Four-on-the-floor claps, slightly offset stereo doubles in drops.
    if b>=8 and sec not in ('break','outro'):
        for beat in (1,3):
            put(drums, at(b,beat), CLAP, -.08, .43)
            if sec in ('drop','drop2'):
                put(drums, at(b,beat)+int(.006*SR), CLAP, .16, .11)
    if b>=32 and b<40:
        # Airy half-time claps in the breakdown.
        if b>=36:
            put(drums,at(b,3),CLAP,.05,.24)
    # Percussion: shuffled offbeat hats, 16th ticks, and occasional metallic open hat.
    for eighth in range(8):
        if b>=2 and (sec!='break' or b>=36):
            if sec in ('drop','drop2') or eighth%2==1:
                put(drums,at(b,eighth*.5),CLOSED, .32 if eighth%2 else -.25, .13 if eighth%2 else .095)
    if sec in ('build','drop','drop2'):
        for step in (3,7,11,15):
            if step%4==3 and (step==7 or (b+step)%3!=0):
                put(drums,at(b,step*.25),CLOSED,.48,.055)
    if (sec in ('build','drop','drop2') and b%2==1) or (sec=='break' and b in (38,39)):
        put(drums,at(b,2),OPEN,.35,.22)
    # Muted synth chords, opening up at each build and the two main drops.
    chord_on = b>=6 and (sec!='outro' or b<61)
    if chord_on and sec!='break':
        duration=1.75 if sec in ('drop','drop2') else 3.65
        bright=1.2 if sec in ('drop','drop2') else .55+(b%8)*.08
        s=chord([440*2**((m-69)/12) for m in voicing],duration,bright)
        put(music,at(b,0),s,.0,.16 if sec in ('drop','drop2') else .11)
        if sec in ('drop','drop2'):
            # Offbeat chord stab adds a bright, springy answer to the bass.
            put(music,at(b,2),chord([440*2**((m-69)/12) for m in voicing],.38,1.5),.08,.10)
    # Acid sequence in sixteenths; accents, skips, octave jumps and cutoff movement are sequenced.
    if b>=4 and sec!='break' and b<62:
        pattern=[0,0,7,12,0,7,3,7,0,0,10,12,7,3,0,7]
        for step,offset in enumerate(pattern):
            active=(step not in (6,14) or b%2==1)
            if sec=='intro': active=step in (0,4,8,12) and b>=6
            if sec=='build': active=(step%2==0 or (b>=12 and step in (3,7,11,15)))
            if sec=='outro': active=step in (0,4,8,12) and b<60
            if not active: continue
            # Root note shifts with the four-bar harmony; accent pattern advances every bar.
            f=root*2**(offset/12)
            if step in (3,11): f*=2
            dur=.105 if step not in (3,11) else .16
            cutoff=(1500,2600,3700,2100)[(step+b)%4] + (1700 if step in (3,11) else 0)
            accent=1.35 if step in (0,3,7,11,15) else .82
            sig=bass_note(f,dur,cutoff,accent)
            put(music,at(b,step*.25),sig,-.10 if step%2 else .10,.29 if sec in ('drop','drop2') else .22)
            # Sub tracks only the first and third beat, keeping club-weight without mud.
            if step in (0,8) and sec in ('drop','drop2','build'):
                put(music,at(b,step*.25),sub_note(root,dur*1.8),0,.30)
    # Main hook, introduced as a teaser, full and harmonically doubled in the drops.
    if (sec in ('drop','drop2') or (sec=='build' and b>=12) or (sec=='intro' and b==7)):
        for beat,note,dur in melody:
            if sec=='build' and b%2==0: continue
            # Vary motif response on alternate four-bar phrases while retaining the singable contour.
            pitch=note + (0 if (b//4)%2==0 else (-2 if beat>=4 else 0))
            freq=440*2**((pitch-69)/12)
            pan=(-.28 if int(beat*2)%2 else .24)
            sig=lead_note(freq,dur,1.0)
            put(music,at(b,beat),sig,pan,.22 if sec in ('drop','drop2') else .14)
            if sec in ('drop','drop2') and beat in (1.5,4,7):
                # Octave shimmer is a melodic counter-hook, not noise.
                put(music,at(b,beat)+int(.012*SR),lead_note(freq*2,dur*.8,.75),-.34,.055)
    # Breakdown: wide, slow, filtered chord wash and a brief exposed lead fragment.
    if sec=='break':
        if b in (32,34,36,38):
            wash=chord([440*2**((m-69)/12) for m in voicing],3.55,.5)
            put(music,at(b),wash, -.16 if b%4==0 else .16,.25)
        if b in (34,38):
            for j,note in enumerate((74,77,81,84)):
                put(music,at(b,j*.75),lead_note(440*2**((note-69)/12),.48,.45),.2,.10)
    # Soft riser sweeps into both drops, built from tonal partials plus only a whisper of filtered air.
    if b in (15,39,55):
        length=int(BAR*SR); t=np.arange(length,dtype=np.float32)/SR
        rise=t/BAR
        tonal=(np.sin(2*np.pi*(220+900*rise)*t)+.5*np.sin(2*np.pi*(330+1500*rise)*t))*rise**1.8
        air=bandpass(rng.standard_normal(length).astype(np.float32),1600,10000)*.045*rise**2
        sweep=softclip((tonal*.10+air)*np.sin(np.pi*rise/2),1.1)
        put(fx,at(b),sweep,.0,.45)

# Break the synth bus with the kick, while letting the kick transient itself stay solid.
t=np.arange(N,dtype=np.float32)/SR
beat_phase=np.mod(t,BEAT)
# Fast dip, smooth return: classic dance-floor sidechain pump.
pump=1.0-.34*np.exp(-beat_phase/.105)
# Let breakdown breathe, and ease the final outro naturally.
for b in range(32,36): pump[int(b*BAR*SR):int((b+1)*BAR*SR)] = 1.0
music *= pump[:,None]

# Stereo ping-pong echoes on melodic material and a pair of dark, short room reflections.
wet=music.copy()
delay=int(.375*SR)
wet[delay:,0] += music[:-delay,1]*.19
wet[delay:,1] += music[:-delay,0]*.23
for d,g,swap in [(int(.75*SR),.105,False),(int(1.125*SR),.055,True),(int(.047*SR),.065,True),(int(.071*SR),.045,False)]:
    if swap:
        wet[d:,0] += music[:-d,1]*g; wet[d:,1] += music[:-d,0]*g
    else:
        wet[d:] += music[:-d]*g
mix=drums + wet*.82 + fx
# Gentle bus saturation and a transparent final limiter.
mix=np.tanh(mix*1.16)/1.16
peak=np.max(np.abs(mix))
if peak>.94: mix*=.94/peak
# 24-bit-equivalent floating render converted to high-quality 16-bit PCM for universal playback.
path=Path('output/NEON_AFTERBURN.wav')
path.parent.mkdir(parents=True,exist_ok=True)
write(path,SR,np.asarray(np.clip(mix,-1,1)*32767,np.int16))
print(f'Wrote {path} | {DURATION:.2f}s | {SR} Hz stereo | peak {peak:.3f}')
