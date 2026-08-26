// NPC definitions
export const NPCS = {
  receptionist: {
    name: 'Receptionist',
    greeting: 'Welcome to Cheetos Co.! I\'m the receptionist. How can I help you?',
    dialogue: [
      { text: 'This is the main lobby. You can access different areas through the hallway.' },
      { text: 'Make sure to check in with HR before starting your shift.' },
      { choices: [
        { text: 'Where is HR?', action: () => {} },
        { text: 'Thanks!', action: () => {} }
      ]}
    ]
  },
  
  janitor: {
    name: 'Janitor',
    greeting: 'Oh, hello there. New employee?',
    dialogue: [
      { text: 'I\'ve been cleaning these halls for 20 years. Seen a lot of people come and go.' },
      { text: 'Watch out for the machines in the cooking room. They can be dangerous if not handled properly.' },
      { choices: [
        { text: 'Any advice?', action: () => {} },
        { text: 'I\'ll be careful.', action: () => {} }
      ]}
    ]
  }
};
