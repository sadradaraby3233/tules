// Item definitions
export const ITEMS = {
  // Ingredients
  corn_meal: {
    name: 'Corn Meal',
    description: 'Ground corn for making snacks',
    value: 5,
    stackable: true
  },
  
  cheese_powder: {
    name: 'Cheese Powder',
    description: 'Artificial cheese flavoring',
    value: 3,
    stackable: true
  },
  
  oil: {
    name: 'Cooking Oil',
    description: 'Vegetable oil for frying',
    value: 4,
    stackable: true
  },
  
  salt: {
    name: 'Salt',
    description: 'Seasoning salt',
    value: 2,
    stackable: true
  },
  
  // Products
  cheetos: {
    name: 'Cheetos',
    description: 'Crunchy cheese-flavored snack',
    value: 15,
    stackable: true
  },
  
  doritos: {
    name: 'Doritos',
    description: 'Triangular corn chips',
    value: 18,
    stackable: true
  },
  
  chips: {
    name: 'Potato Chips',
    description: 'Classic salted potato chips',
    value: 12,
    stackable: true
  },
  
  // Tools
  wrench: {
    name: 'Wrench',
    description: 'For fixing machines',
    value: 25,
    stackable: false
  },
  
  // Special
  employee_badge: {
    name: 'Employee Badge',
    description: 'Your Cheetos Co. employee ID',
    value: 0,
    stackable: false,
    unique: true
  }
};
