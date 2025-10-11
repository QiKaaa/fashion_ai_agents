import re
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.logging import app_logger
from app.models.database import get_db


class SQLDataImporter:
    """数据导入器，从数据库或SQL文件中提取产品数据用于向量化"""
    
    def get_products_from_database(self) -> List[Dict[str, Any]]:
        """直接从数据库products表获取产品数据用于向量化
        
        Returns:
            产品数据列表
        """
        try:
            with next(get_db()) as db:
                # 直接查询products表
                query = """
                SELECT 
                    id,
                    product_name,
                    description,
                    image_gif,
                    category_id,
                    brand,
                    price,
                    is_recommended,
                    product_status,
                    scene,
                    create_time,
                    update_time,
                    deleted
                FROM products 
                WHERE deleted = 0 OR deleted IS NULL
                ORDER BY id
                """
                
                result = db.execute(text(query))
                products = []
                
                for row in result:
                    product = {
                        'id': row[0],
                        'product_id': row[0],  # 保持兼容性
                        'product_name': row[1],
                        'description': row[2] or '',
                        'image_gif': row[3] or '',
                        'category_id': row[4],
                        'brand': row[5],
                        'price': float(row[6]) if row[6] else 0.0,
                        'is_recommended': row[7] or 0,
                        'product_status': row[8] or 0,
                        'scene': self._validate_scene(row[9] or 'casual'),
                        'create_time': row[10],
                        'update_time': row[11],
                        'deleted': row[12] or 0,
                        # 从商品信息推断的属性
                        'color': self._infer_color(row[1], row[2] or ''),
                        'style': self._infer_style(row[1], row[2] or ''),
                        'fit': self._infer_fit(row[1], row[2] or ''),
                        'material': self._infer_material(row[1], row[2] or ''),
                        'season': self._infer_season(row[1], row[2] or ''),
                        'pattern': self._infer_pattern(row[1], row[2] or '')
                    }
                    products.append(product)
                
                app_logger.info(f"从数据库products表获取到 {len(products)} 个产品")
                return products
                
        except Exception as e:
            app_logger.error(f"从数据库获取产品数据失败: {e}")
            return []
    
    def get_products_for_vectorization(self, sql_files: List[str]) -> List[Dict[str, Any]]:
        """从SQL文件中提取产品数据用于向量化
        
        Args:
            sql_files: SQL文件路径列表
            
        Returns:
            产品数据列表
        """
        all_products = []
        
        for sql_file in sql_files:
            app_logger.info(f"解析SQL文件: {sql_file}")
            products = self._extract_products_from_sql_file(sql_file)
            all_products.extend(products)
        
        app_logger.info(f"总共提取到 {len(all_products)} 个产品")
        
        return all_products
    
    def _extract_products_from_sql_file(self, file_path: str) -> List[Dict[str, Any]]:
        """从SQL文件中提取产品数据，直接从products表获取所有信息"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # 提取products表数据
            products = self._extract_products_data(content)
            
            app_logger.info(f"从 {file_path} 中提取到 {len(products)} 个产品")
            return products
            
        except Exception as e:
            app_logger.error(f"解析SQL文件失败: {e}")
            return []
    
    def _extract_products_data(self, content: str) -> List[Dict[str, Any]]:
        """提取products表的数据"""
        products = []
        # 匹配products表的INSERT语句
        pattern = r'INSERT INTO "products" \([^)]+\)\s+VALUES\s*\((.*?)\);'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for values_str in matches:
            product_data = self._parse_products_values(values_str)
            if product_data:
                products.append(product_data)
        
        return products
    
    def _parse_products_values(self, values_str: str) -> Optional[Dict[str, Any]]:
        """解析products表的VALUES字符串"""
        try:
            # 使用正则表达式匹配SQL中的值
            pattern = r"'([^']*)'|(\d+\.?\d*)|(CURRENT_TIMESTAMP)"
            matches = re.findall(pattern, values_str)
            
            # 提取字段值
            values = []
            for match in matches:
                if match[0]:  # 字符串
                    values.append(match[0])
                elif match[1]:  # 数字
                    if '.' in match[1]:
                        values.append(float(match[1]))
                    else:
                        values.append(int(match[1]))
                elif match[2]:  # CURRENT_TIMESTAMP
                    values.append(match[2])
            
            # 根据products表结构映射字段
            if len(values) >= 12:
                # 从商品名称和描述中推断属性
                product_name = values[1]
                description = values[2]
                
                return {
                    'id': values[0],
                    'product_id': values[0],  # 保持兼容性
                    'product_name': product_name,
                    'description': description,
                    'image_gif': values[3],
                    'category_id': values[4],
                    'brand': values[5],
                    'price': values[6],
                    'is_recommended': values[7],
                    'product_status': values[8],
                    'scene': self._validate_scene(values[9] if len(values) > 9 else 'casual'),
                    'create_time': values[10] if len(values) > 10 else None,
                    'update_time': values[11] if len(values) > 11 else None,
                    'deleted': values[12] if len(values) > 12 else 0,
                    # 从商品信息推断的属性
                    'color': self._infer_color(product_name, description),
                    'style': self._infer_style(product_name, description),
                    'fit': self._infer_fit(product_name, description),
                    'material': self._infer_material(product_name, description),
                    'season': self._infer_season(product_name, description),
                    'pattern': self._infer_pattern(product_name, description)
                }
            
        except Exception as e:
            app_logger.warning(f"解析products VALUES字符串失败: {e}")
        
        return None
    
    def _infer_color(self, product_name: str, description: str) -> str:
        """从商品名称和描述中推断颜色"""
        text = f"{product_name} {description}".lower()
        
        color_keywords = {
            'black': '黑色', 'white': '白色', 'red': '红色', 'blue': '蓝色', 'green': '绿色',
            'yellow': '黄色', 'pink': '粉色', 'purple': '紫色', 'orange': '橙色', 'brown': '棕色',
            'gray': '灰色', 'grey': '灰色', 'navy': '海军蓝', 'beige': '米色', 'khaki': '卡其色'
        }
        
        for eng, chn in color_keywords.items():
            if eng in text or chn in text:
                return chn
        
        return '其他'
    
    def _infer_style(self, product_name: str, description: str) -> str:
        """从商品名称和描述中推断风格"""
        text = f"{product_name} {description}".lower()
        
        if any(word in text for word in ['休闲', 'casual', '宽松', '舒适']):
            return 'casual'
        elif any(word in text for word in ['运动', 'sports', '健身', '训练', '跑步']):
            return 'sports'
        elif any(word in text for word in ['正式', 'formal', '商务', '西装']):
            return 'formal'
        elif any(word in text for word in ['派对', 'party', '晚宴', '礼服']):
            return 'party'
        else:
            return 'casual'
    
    def _infer_fit(self, product_name: str, description: str) -> str:
        """从商品名称和描述中推断版型"""
        text = f"{product_name} {description}".lower()
        
        if any(word in text for word in ['宽松', 'loose', 'oversized', '超宽松']):
            return 'loose'
        elif any(word in text for word in ['紧身', 'tight', '修身', '贴身']):
            return 'tight'
        elif any(word in text for word in ['直筒', 'straight', 'regular']):
            return 'regular'
        else:
            return 'regular'
    
    def _infer_material(self, product_name: str, description: str) -> str:
        """从商品名称和描述中推断材质"""
        text = f"{product_name} {description}".lower()
        
        if any(word in text for word in ['棉', 'cotton', '纯棉', '棉质']):
            return 'cotton'
        elif any(word in text for word in ['丝', 'silk', '丝绸', '真丝']):
            return 'silk'
        elif any(word in text for word in ['麻', 'linen', '亚麻']):
            return 'linen'
        elif any(word in text for word in ['毛', 'wool', '羊毛', '针织']):
            return 'wool'
        elif any(word in text for word in ['牛仔', 'denim', '牛仔布']):
            return 'denim'
        else:
            return 'cotton'
    
    def _infer_season(self, product_name: str, description: str) -> str:
        """从商品名称和描述中推断季节"""
        text = f"{product_name} {description}".lower()
        
        if any(word in text for word in ['春', 'spring', '春季']):
            return 'spring'
        elif any(word in text for word in ['夏', 'summer', '夏季', '短袖', '短裤']):
            return 'summer'
        elif any(word in text for word in ['秋', 'autumn', 'fall', '秋季']):
            return 'autumn'
        elif any(word in text for word in ['冬', 'winter', '冬季', '羽绒', '棉服']):
            return 'winter'
        else:
            return 'all'
    
    def _infer_pattern(self, product_name: str, description: str) -> str:
        """从商品名称和描述中推断图案"""
        text = f"{product_name} {description}".lower()
        
        if any(word in text for word in ['纯色', 'solid', '净色', '素色']):
            return 'solid'
        elif any(word in text for word in ['条纹', 'stripe', '条纹']):
            return 'stripe'
        elif any(word in text for word in ['格子', 'check', '格纹']):
            return 'check'
        elif any(word in text for word in ['印花', 'print', '图案']):
            return 'print'
        elif any(word in text for word in ['字母', 'logo', '字母印花']):
            return 'logo'
        else:
            return 'solid'
    
    def _validate_scene(self, scene: str) -> str:
        """验证场景值，只允许casual和sports"""
        valid_scenes = {'casual', 'sports'}
        if scene in valid_scenes:
            return scene
        else:
            app_logger.warning(f"无效的场景值: {scene}，使用默认值: casual")
            return 'casual'