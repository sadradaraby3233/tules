# 🧀 Cheetos Factory: Audio Ops - Blind Accessible Audio Game

**100% Procedural Audio • No Images • Fully Blind Accessible • Cross-Platform**

A first-person audio adventure where you get recruited into the Cheetos company. Walk around the factory using 3D binaural audio, talk to co-workers, collect cornmeal, mix dough, extrude shapes, fry, season, pack, and sell!

## Features

- **Zero visuals gameplay**: Black screen, all info via speech synthesis + procedural earcons
- **Procedural DSP**: Every sound synthesized with Web Audio API - no samples. White/pink noise, oscillators, filters, HRTF panning
- **3D Audio**: HRTF PannerNode beacons for exits. Left/right/front/back detection. Test speakers mode with circling sound
- **Cross-platform**: Keyboard (WASD/Arrows/Enter/I/H/Space/ESC/M/E) + Touch (swipe, tap, on-screen buttons)
- **Massive Data-Driven**: All content in `GAME_DATA` object - easy to expand

## How to Play (Audio Guide)

1. **TAP / CLICK** overlay to initialize audio (required by browsers). On Windows, any key also tries auto-init
2. Main Menu (spoken):
   - Start New Shift
   - Continue Shift (if save in localStorage)
   - Test Speakers (L/R/Center/Circle)
   - How to Play
   - Settings (speech rate, 3D toggle)

3. **Movement**:
   - W/↑ = North/Forward
   - S/↓ = South/Back
   - A/← = West/Left
   - D/→ = East/Right
   - Q = Turn left 90°, E = Interact
   - Touch: Swipe or use bottom arrow buttons. Tap log area = interact

4. **Interaction**:
   - ENTER / SPACE / Center ● button = Interact with nearest NPC/object/machine
   - When multiple options, audio menu appears: ↑↓ navigate, ENTER select
   - SPACE (in game) = Scan room + play 3D beacons for exits

5. **Crafting Loop**:
   - Corn Silo (Warehouse North) = collect free cornmeal
   - Mixing Lab (HR North) = Mix dough: 2 corn + 1 water (water from cooler)
   - Extruder Floor (Mixing East) = Dough -> Crunchy shape or Puff shape
   - Fryer Room (Seasoning South) = Shapes + Oil -> Fried base
   - Seasoning Tunnel = Fried base + Cheese/Flamin dust -> Seasoned
   - Packaging Line = Seasoned -> Final bag
   - Market (Warehouse West) = Sell bags for $

6. **Other**:
   - I = Inventory
   - H = Help / describe room
   - ESC = Pause menu (Save, etc)
   - M = Quick machine menu

## Data-Driven Expansion

Edit `GAME_DATA` at top of `index.html`:

### Add New Ingredient
```js
ingredients: {
  myNewDust: { id:'myNewDust', name:'My Dust', desc:'...', value:10, sound:'puff_powder', free:false, buyPrice:15 }
}
```

### Add New Recipe / Process
```js
processes: [
  {
    id:'pack-my-new', name:'Pack My New Cheetos', desc:'...',
    machine:'packager', // mixer, extruder, fryer, oven, seasoningDrum, packager
    inputs:{classicSeasoned:1},
    outputs:{'my-new-bag':1},
    xp:20, value:35, sound:'packager', unlockLevel:2, final:true
  }
]
```

### Add New Room
```js
rooms: {
  'my-room': {
    id:'my-room', name:'My Room', desc:'Audio description...',
    ambience:'lab', // lobby, office, lab, mixer, silo, warehouse, extruder, seasoning, fryer, packager, market, chester
    exits:{north:'lobby', south:'market'},
    objects:[{id:'my-object', name:'My Object', desc:'...'}],
    npcs:['my-npc'], machines:['mixer']
  }
}
```

### Add New NPC
```js
npcs: {
  'my-npc': {
    id:'my-npc', name:'My NPC', room:'my-room',
    voice:{base:200, rate:1.0, vibrato:2},
    greet:'Hello!',
    dialogues:[{id:'hi', text:'I sell stuff', quest:'my-quest'}]
  }
}
```

### Add New Machine
```js
machines: {
  myMachine: { id:'myMachine', name:'My Machine', desc:'...', room:'my-room', sound:'mixer', beaconFreq:500 }
}
```

All systems automatically use new data - no engine changes needed!

## Audio Engine - Procedural Sounds

All in `AudioEngine` class:

- `tone({freq, duration, type, volume, pan, x,y,z})` - 3D positioned tone
- `noiseTone({duration, type, filterFreq, volume})` - filtered noise
- `playIngredientSound(id)` - corn pour, cheese puff, etc
- `playMachineSound(machineId)` - mixer, extruder, fryer, seasoning, packager
- `playExitBeacon(dir, angle)` - HRTF beacon for navigation
- `startAmbience(roomId)` - procedural room drones
- `speak(text)` - Web Speech API + aria-live
- `testSpeakers()` - L/R/Center/Circle demo

Ambience per room: low hums, noise loops, random ticks. No samples!

## Save System

- Auto-saves on room enter, craft, level up, quest complete
- Manual save in pause menu
- Key: `cheetosAudioFactorySave_v1` in localStorage
- Contains inventory, money, xp, level, location, quests

## Quests

- Tutorial: Make 1 Classic Crunchy
- Unlock XXXtra: Bring 3 Classic to Dr. Powder
- Chester Final: Bring one of each bag to Chester (Level 5 required for office)

## Levels

1 Intern, 2 Line Worker (Flamin), 3 Flavor Tech (Jalapeño/Baked), 4 Senior Tech (Honey BBQ), 5 Chester Elite (XXXtra + Chester office), 6 Legend

## Accessibility Notes

- All UI has `aria-label`, `aria-live` regions
- Speech rate adjustable in settings (0.5x - 2.0x)
- 3D audio can be toggled to stereo for mono speakers
- High contrast log for sighted helpers but game playable blindfolded
- No time pressure, no visual puzzles
- Works with screen readers (NVDA, JAWS, VoiceOver) + game speech

## Running

Just open `index.html` in browser, or:
```
python -m http.server 8000
```
Then open http://localhost:8000

Headphones strongly recommended!

## Tech Stack

- Single HTML file, vanilla JS, no dependencies
- Web Audio API: OscillatorNode, BiquadFilter, PannerNode (HRTF), StereoPanner, Gain, BufferSource
- Web Speech API: speechSynthesis
- localStorage for saves
- Touch + Keyboard + Gamepad-ready structure

Enjoy! Make it awesomely awesome! 🧀🔥
