// 界面演示数据 —— 仅用于让 Web Demo 脱离网络独立打开，不作为营养真值来源。
// 真实运行时的热量必须来自麦当劳 MCP 的 list-nutrition-foods 工具，
// 由 skill/scripts/nutrition_calculator.py 统一计算，本文件不参与计算链路。
// 数值为公开营养信息的整理快照，仅供演示交互。
window.MENU = [
  { id: 'm1', name: '巨无霸', cat: '汉堡', kcal: 550, p: 25, f: 30, c: 46, tags: ['高热量', '经典'], price: 22, img: '🍔' },
  { id: 'm2', name: '板烧鸡腿堡', cat: '汉堡', kcal: 480, p: 28, f: 24, c: 40, tags: ['经典'], price: 21, img: '🍔' },
  { id: 'm3', name: '麦辣鸡腿汉堡', cat: '汉堡', kcal: 520, p: 26, f: 29, c: 42, tags: ['辣', '高热量'], price: 23, img: '🍔' },
  { id: 'm4', name: '麦香鸡', cat: '汉堡', kcal: 500, p: 25, f: 26, c: 43, tags: ['经典'], price: 22, img: '🍔' },
  { id: 'm5', name: '吉士汉堡堡', cat: '汉堡', kcal: 430, p: 24, f: 21, c: 36, tags: ['芝士'], price: 21, img: '🍔' },
  { id: 'm6', name: '双层吉士汉堡', cat: '汉堡', kcal: 640, p: 33, f: 34, c: 48, tags: ['高热量'], price: 28, img: '🍔' },

  { id: 's1', name: '中薯条', cat: '小食', kcal: 240, p: 4, f: 12, c: 30, tags: ['油炸'], price: 7, img: '🍟' },
  { id: 's2', name: '大薯条', cat: '小食', kcal: 340, p: 5, f: 17, c: 42, tags: ['油炸'], price: 10, img: '🍟' },
  { id: 's3', name: '麦乐鸡（5块）', cat: '小食', kcal: 260, p: 15, f: 16, c: 13, tags: ['油炸'], price: 12, img: '🍗' },
  { id: 's4', name: '麦乐鸡（10块）', cat: '小食', kcal: 520, p: 30, f: 32, c: 26, tags: ['油炸'], price: 21, img: '🍗' },
  { id: 's5', name: '黄金薯饼', cat: '小食', kcal: 230, p: 4, f: 14, c: 24, tags: ['油炸'], price: 8, img: '🥔' },
  { id: 's6', name: '香辣鸡腿堡（麦辣鸡块）', cat: '小食', kcal: 180, p: 10, f: 11, c: 11, tags: ['油炸'], price: 9, img: '🍗' },

  { id: 'd1', name: '可乐（中）', cat: '饮品', kcal: 140, p: 0, f: 0, c: 36, tags: ['含糖'], price: 7, img: '🥤' },
  { id: 'd2', name: '无糖可乐（中）', cat: '饮品', kcal: 2, p: 0, f: 0, c: 0, tags: ['零卡'], price: 7, img: '🥤' },
  { id: 'd3', name: '雪碧（中）', cat: '饮品', kcal: 150, p: 0, f: 0, c: 38, tags: ['含糖'], price: 7, img: '🥤' },
  { id: 'd4', name: '鲜煮咖啡（中）', cat: '饮品', kcal: 5, p: 0, f: 0, c: 1, tags: ['低卡'], price: 10, img: '☕' },
  { id: 'd5', name: '美式咖啡', cat: '饮品', kcal: 5, p: 0, f: 0, c: 1, tags: ['低卡'], price: 12, img: '☕' },
  { id: 'd6', name: '温热鲜奶', cat: '饮品', kcal: 130, p: 8, f: 7, c: 12, tags: ['含乳'], price: 9, img: '🥛' },

  { id: 'ds1', name: '麦旋风（奥利奥）', cat: '甜品', kcal: 340, p: 6, f: 21, c: 35, tags: ['高糖'], price: 13, img: '🍨' },
  { id: 'ds2', name: '新地（草莓/巧克力）', cat: '甜品', kcal: 270, p: 5, f: 12, c: 34, tags: ['高糖'], price: 9, img: '🍨' },
  { id: 'ds3', name: '红豆派', cat: '甜品', kcal: 250, p: 4, f: 14, c: 29, tags: ['高糖'], price: 7, img: '🥮' }
];