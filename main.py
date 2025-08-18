import time
import random
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("world", "ZY霆生", "星铁World", "1.0.0")
class MyPlugin(Star):
    @filter.regex("^创建展会(.*)$")
    async def create_user(self, event: AstrMessageEvent):
        """创建展会"""
        import os, re
        # 检查保存路径是否存在
        if not os.path.exists(self.savePath):
            os.makedirs(self.savePath, 0o755, True)

        # 检查是否已创建过展会
        player = self.load_player(event)
        if player:
            yield event.make_result().message(f"你已经创建过展会：{player['name']} 了。")
            return

        # 获取展会名称
        name = event.message_str.replace("创建展会", "").strip()
        if not name:
            yield event.make_result().message("展会名称不可为空，请使用 \"创建展会 你的展会名\"")
            return

        # 检查名称长度
        if len(name) > 20:
            yield event.make_result().message("展会名称过长，请使用20个字符以内的名称")
            return

        # 检查敏感词
        if self.contains_banned_words(name):
            yield event.make_result().message("展会名称包含不当内容，请更换一个合适的名称")
            return

        # 检查特殊字符
        if re.search(r'[<>"\'\\\\\\/]', name):
            yield event.make_result().message("展会名称不能包含特殊字符，请重新输入")
            return

        # 检查重名
        if self.check_name_exists(name):
            yield event.make_result().message(f"展会名称「{name}」已被占用，请更换另一个名字")
            return

        # 创建展会
        player = self.get_default_player(name)
        self.save_player(event, player)
        yield event.make_result().message(
            f"展会创建成功！欢迎你，{name}。\n你已拥有第一个展台：咖啡馆。\n\n【新手引导】\n1️⃣ 首先，使用'普通邀约'来获得你的第一个助理\n2️⃣ 然后，使用'分配助理 助理名 咖啡馆'将助理分配到展区\n3️⃣ 最后，使用'一键收取'来获取收益\n\n如需帮助请输入'展会指令'查看指令。"
        )
    
    def __init__(self, context: Context):
        super().__init__(context)
        # 在__init__方法中定义实例变量
        self.plugin_name = "星铁World插件"
        self.version = "1.0.0"
        self.counter = 0
        self.config = {"enable_logging": True}
        self.useArkReply = True  # 是否使用ArkReply格式回复消息
        self.savePath = "data/plugins/astrbot_plugin_srwolrd/save" # 保存路径
        self.worldPath = "data/plugins/astrbot_plugin_srwolrd/world.json" # 世界路径
        self.database = None
        self.booths = {
            '咖啡馆': {'area': '消费展区', 'unlock_cost': '10K', 'base_income': '1K', 'unlocked': False},
            '便利店': {'area': '消费展区', 'unlock_cost': '100K', 'base_income': '5K', 'unlocked': False},
            '服装店': {'area': '消费展区', 'unlock_cost': '1M', 'base_income': '20K', 'unlocked': False},
            '电玩城': {'area': '趣味展区', 'unlock_cost': '10M', 'base_income': '100K', 'unlocked': False},
            'KTV': {'area': '趣味展区', 'unlock_cost': '100M', 'base_income': '500K', 'unlocked': False},
            '电影院': {'area': '趣味展区', 'unlock_cost': '1G', 'base_income': '2M', 'unlocked': False},
            '书店': {'area': '纪念展区', 'unlock_cost': '10G', 'base_income': '10M', 'unlocked': False},
            '培训班': {'area': '纪念展区', 'unlock_cost': '100G', 'base_income': '50M', 'unlocked': False},
            '科技馆': {'area': '纪念展区', 'unlock_cost': '1AA', 'base_income': '200M', 'unlocked': False},
        }
        self.assistant_pool = {
            '普通': {'cost': 100, 'rates': {'见习': 0.8, '熟练': 0.18, '资深': 0.02}},
            '黄金': {'cost': 300, 'rates': {'见习': 0.5, '熟练': 0.4, '资深': 0.1}},
            '炫彩': {'cost': 500, 'rates': {'见习': 0.2, '熟练': 0.5, '资深': 0.3}},
        }
        self.star_upgrade_cost = {
            1: 3,  # 1星升2星需要3个碎片
            2: 10, # 2星升3星需要10个碎片
            3: 20, # 3星升4星需要20个碎片
        }
        self.level_upgrade_base_cost = 1000  # 初始升级费用
        self.level_upgrade_multiplier = 1.13  # 每级升级费用倍率
        self.units = ['', 'K', 'M', 'G', 'AA', 'BB', 'CC', 'DD', 'EE', 'FF', 'GG', 'HH', 'II', 'JJ', 'KK', 'LL', 'MM', 'NN', 'OO', 'PP', 'QQ', 'RR', 'SS', 'TT', 'UU', 'VV', 'WW', 'XX', 'YY', 'ZZ']
        self.all_assistant_data_cache = None
        self.banned_words_cache = None
        self.api_config_cache = None
        self.api_result_cache = {}
        self.is_initialized = False  # 标记插件是否已初始化
        self.random = random  # 添加random引用

    def get_database(self):
        if self.database is None:
            from .Database import IdleTycoonDatabase
            self.database = IdleTycoonDatabase.get_instance()
            # 确保数据库表已创建（备用机制）
            try:
                # 测试一个基础查询，如果失败说明表不存在
                with self.database.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM players LIMIT 1")
            except Exception as e:
                # 如果查询失败，尝试创建表
                try:
                    print("检测到数据库表不存在，正在创建...")
                    self.database.create_tables()
                    print("数据库表创建完成")
                except Exception as create_error:
                    print(f"创建数据库表失败: {create_error}")
        return self.database

    def load_banned_words(self):
        if self.banned_words_cache is None:
            import os
            banned_words_file = os.path.join(os.path.dirname(__file__), 'banned_words.json')
            if os.path.exists(banned_words_file):
                import json
                with open(banned_words_file, 'r', encoding='utf-8') as f:
                    banned_words_data = json.load(f)
                    if banned_words_data:
                        self.banned_words_cache = []
                        for category, words in banned_words_data.items():
                            self.banned_words_cache.extend(words)
                    else:
                        self.banned_words_cache = []
            else:
                # 默认违禁词列表
                self.banned_words_cache = [
                    '不当词1',
                    '不当词2',
                    '不当词3'
                ]
        return self.banned_words_cache

    def load_api_config(self):
        if self.api_config_cache is None:
            import os
            import json
            config_file = os.path.join(os.path.dirname(__file__), 'api_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self.api_config_cache = config_data if config_data else {}
            else:
                # 默认API配置
                self.api_config_cache = {
                    'banned_words_api': {
                        'enabled': True,
                        'url': 'https://v2.xxapi.cn/api/detect',
                        'timeout': 5,
                        'confidence_threshold': 0.7,
                        'fallback_to_local': True
                    }
                }
        return self.api_config_cache
        
    def check_banned_words_api(self, text):
        """使用API检测违禁词"""
        import time
        import hashlib
        import requests
        
        config = self.load_api_config()
        api_config = config.get('banned_words_api', {})
        
        # 检查API是否启用
        if not api_config.get('enabled', True):
            return {'success': False, 'error': 'API已禁用'}
        
        # 检查缓存
        cache_key = hashlib.md5(text.encode('utf-8')).hexdigest()
        if cache_key in self.api_result_cache:
            cached = self.api_result_cache[cache_key]
            if time.time() - cached['timestamp'] < 3600:  # 1小时缓存
                return cached['result']
        
        try:
            url = api_config.get('url', 'https://v2.xxapi.cn/api/detect')
            timeout = api_config.get('timeout', 5)
            
            response = requests.get(
                url,
                params={'text': text},
                timeout=timeout
            )
            
            if response.status_code != 200:
                logger.info(f"违禁词API返回错误状态码: {response.status_code}")
                return {'success': False, 'error': f"HTTP {response.status_code}"}
            
            data = response.json().get('data')
            if not data:
                logger.info(f"违禁词API返回无效JSON: {response.text}")
                return {'success': False, 'error': '无效响应'}
            
            result = {
                'success': True,
                'is_prohibited': data.get('is_prohibited', False),
                'confidence': data.get('confidence', 0),
                'max_variant': data.get('max_variant', ''),
                'triggered_variants': data.get('triggered_variants', [])
            }
            
            # 缓存结果
            self.api_result_cache[cache_key] = {
                'result': result,
                'timestamp': time.time()
            }
            
            # 记录日志
            if config.get('logging', {}).get('log_api_calls', False):
                status = "违禁" if result['is_prohibited'] else "正常"
                logger.info(f"违禁词API调用: {text} -> {status} (置信度: {result['confidence']}) raw: {response.text}")
            
            return result
            
        except Exception as e:
            logger.info(f"违禁词API检测异常: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def contains_banned_words(self, name):
        """检查名称是否包含敏感词（本地词库 + API检测）"""
        config = self.load_api_config()
        local_config = config.get('local_detection', {})
        api_config = config.get('banned_words_api', {})
        
        # 1. 本地词库检测（快速）
        if local_config.get('enabled', True):
            banned_words = self.load_banned_words()
            name_lower = name.lower()
            for banned_word in banned_words:
                if banned_word.lower() in name_lower:
                    if config.get('logging', {}).get('log_detected_words', False):
                        logger.info(f"本地词库检测到敏感词: {name} -> {banned_word}")
                    return True
        
        # 2. API检测（更准确但较慢）
        if api_config.get('enabled', True):
            api_result = self.check_banned_words_api(name)
            if api_result.get('success'):
                confidence = api_result.get('confidence', 0)
                threshold = api_config.get('confidence_threshold', 0.7)
                
                if api_result.get('is_prohibited') and confidence >= threshold:
                    if config.get('logging', {}).get('log_detected_words', False):
                        logger.info(f"API检测到违禁词: {name} -> {api_result.get('max_variant')} (置信度: {confidence})")
                    return True
            else:
                # API失败时的处理
                if api_config.get('fallback_to_local', True):
                    # 已经执行过本地检测，直接返回False
                    if config.get('logging', {}).get('log_api_calls', False):
                        logger.info(f"API检测失败，使用本地检测结果: {name}")
                else:
                    # 如果不允许降级到本地检测，可以选择拒绝（更安全）
                    logger.info(f"API检测失败且不允许降级: {name}")
                    return True  # 保守策略：API失败时拒绝
        
        return False
        
    def check_name_exists(self, name):
        """检查展会名称是否已存在"""
        try:
            db = self.get_database()
            with db.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM players WHERE name = %s', (name,))
                count = cursor.fetchone()[0]
                
                return count > 0
        except Exception as e:
            logger.info(f"检查名称重复失败: {str(e)}")
            return False
            # 如果数据库查询失败，降级到文件检查
            # return self.check_name_exists_in_files(name)

    def save_player(self, event: AstrMessageEvent, player_data):
        """保存玩家数据到数据库（优化版本）"""
        try:
            db = self.get_database()
            # 使用带重试机制的保存方法，提高并发环境下的成功率
            return db.save_player_with_retry(event.get_sender_id(), player_data)
        except Exception as e:
            logger.info(f"保存玩家数据失败: {str(e)}")
            return False
            
    def load_player(self, event: AstrMessageEvent):
        """加载玩家数据"""
        try:
            db = self.get_database()
            user_id = event.get_sender_id()
            return db.load_player(user_id)
        except Exception as e:
            logger.info(f"加载玩家数据失败: {str(e)}")
            return None

    def get_save_path(self, event: AstrMessageEvent):
        """获取消息发送者所属的save文件夹路径"""
        return self.savePath + f"/user_{event.get_sender_id()}.json"

    def load_world(self):
        """加载排行数据"""
        try:
            db = self.get_database()
            return db.load_world_ranking()
        except Exception as e:
            logger.info(f"加载排行数据失败: {str(e)}")
            return []

    def update_world_ranking(self, user_id, name, gold, totalIncome):
        """更新世界排行数据"""
        try:
            db = self.get_database()
            return db.update_world_ranking(user_id, name, gold, totalIncome)
        except Exception as e:
            logger.info(f"更新排行数据失败: {str(e)}")
            return False
            
    def format_gold(self, num):
        """格式化金币数量，将数字转换为带单位的字符串"""
        num = float(num)
        unit = 0
        while num >= 1000 and unit < len(self.units) - 1:
            num /= 1000
            unit += 1
        return str(int(num)) + self.units[unit]
        
    def parse_gold(self, gold_str):
        """解析带单位的金币字符串，转换为数字"""
        # 更宽松的正则匹配，允许前后空格和小写字母
        import re
        match = re.match(r'^\s*([0-9.]+)\s*([A-Za-z]*)\s*$', gold_str)
        if match:
            num = float(match.group(1))
            unit_str = match.group(2).upper()
            
            if unit_str in self.units:
                unit = self.units.index(unit_str)
            else:
                # 如果单位不存在但字符串不为空，记录警告
                if unit_str:
                    logger.info(f"[IdleTycoon] Unknown unit: {unit_str} in gold string: {gold_str}")
                unit = 0
                
            result = num * (1000 ** unit)
            return result
            
        return 0

    def get_default_player(self, name):
        """
        获取默认玩家数据
        :param name: 玩家名称
        :return: 包含默认玩家数据的字典
        """
        booths = {}
        for booth, info in self.booths.items():
            booths[booth] = {
                'unlocked': booth == '咖啡馆',
                'assistant': None,
                'last_collect': int(time.time())
            }
        
        # 生成新的玩家ID
        player_id = None
        try:
            db = self.get_database()
            player_id = db.get_next_player_id()
        except Exception as e:
            logger.error(f"生成玩家ID失败: {e}")
            # 如果数据库不可用，使用时间戳作为临时ID
            player_id = int(time.time()) % 1000000
        
        return {
            'name': name,
            'player_id': player_id,
            'gold': 0,
            'diamond': 0,
            'booths': booths,
            'assistants': [],  # 已获得的助理列表
            'fragments': {},   # 助理碎片
            'city_level': 1,
            'total_income': 0,
            'tutorial_step': 1,  # 新手引导步骤
            'tickets': {  # 邀约卡
                '普通': 1,
                '黄金': 0,
                '炫彩': 0
            },
            'last_checkin_date': None,  # 上次签到日期
            'consecutive_checkins': 0,  # 连续签到天数
            # 回忆卡相关字段
            'memory_parts': {},  # 回忆卡碎片
            'memory_cards': {},  # 完整回忆卡
            'memory_tickets': 0,  # 回忆卡抽取券数量
            'memory_effects': [],  # 已激活的回忆卡集齐效果
            # 来宾事件相关字段
            'current_event': None,  # 当前触发的事件
            'event_expire_time': 0  # 事件过期时间
        }
        
    def load_all_assistant_data(self):
        """加载所有助理数据"""
        if self.all_assistant_data_cache is None:
            import os
            import json
            file_path = os.path.join(os.path.dirname(__file__), '[星铁Wolrd]助理名单.json')
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.all_assistant_data_cache = json.load(f)
                        if self.all_assistant_data_cache is None:  # JSON 解析错误
                            self.all_assistant_data_cache = []
                            logger.error(f"助理名单JSON解析错误: {file_path}")
                except Exception as e:
                    self.all_assistant_data_cache = []
                    logger.error(f"加载助理名单失败: {str(e)}")
            else:
                self.all_assistant_data_cache = []  # 文件不存在
                logger.error(f"助理名单文件不存在: {file_path}")
        return self.all_assistant_data_cache

    def load_memory_card_data(self):
        """加载回忆卡数据"""
        if not hasattr(self, '_memory_card_data'):
            import os
            import json
            file_path = os.path.join(os.path.dirname(__file__), '[星铁Wolrd]回忆卡.json')
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self._memory_card_data = json.load(f)
                        if self._memory_card_data is None:
                            self._memory_card_data = {}
                except Exception as e:
                    self._memory_card_data = {}
                    logger.error(f"加载回忆卡数据失败: {str(e)}")
            else:
                self._memory_card_data = {}
                logger.error(f"回忆卡文件不存在: {file_path}")
        return self._memory_card_data

    def load_star_sea_anecdotes(self):
        """加载星海轶闻数据"""
        if not hasattr(self, '_star_sea_anecdotes'):
            import os
            import json
            file_path = os.path.join(os.path.dirname(__file__), '[星铁Wolrd]星海轶闻.json')
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self._star_sea_anecdotes = json.load(f)
                        if self._star_sea_anecdotes is None:
                            self._star_sea_anecdotes = []
                except Exception as e:
                    self._star_sea_anecdotes = []
                    logger.error(f"加载星海轶闻数据失败: {str(e)}")
            else:
                self._star_sea_anecdotes = []
                logger.error(f"星海轶闻文件不存在: {file_path}")
        return self._star_sea_anecdotes

    def get_assistant_static_details(self, assistant_name):
        """
        根据助理名称获取助理的详细信息
        :param assistant_name: 助理名称
        :return: 包含助理详细信息的字典，如果未找到则返回None
        """
        all_data = self.load_all_assistant_data()
        for data in all_data:
            if data['name'] == assistant_name:
                return data
        return None

    def get_memory_card_bonus(self, player):
        """
        计算回忆卡的区域加成
        :param player: 玩家数据字典
        :return: 包含各区域加成倍率的字典
        """
        # 初始化所有可能的区域加成（基础值为0%，即1.0倍率）
        bonus = {
            'all': 0.0,           # 所有展台加成百分比
            '消费展区': 0.0,       # 消费展区加成百分比
            '趣味展区': 0.0,       # 趣味展区加成百分比
            '纪念展区': 0.0,       # 纪念展区加成百分比
            'event': 0.0          # 展会事件加成百分比
        }

        # 加载回忆卡数据以获取每张卡的效果
        memory_card_data = self.load_memory_card_data()
        if not memory_card_data:
            # 如果没有回忆卡数据，返回基础倍率
            return {
                'all': 1.0,
                '消费展区': 1.0,
                '趣味展区': 1.0,
                '纪念展区': 1.0,
                'event': 1.0
            }

        # 遍历玩家拥有的每张回忆卡，累加效果
        if 'memory_cards' in player and player['memory_cards']:
            for card_name, card_count in player['memory_cards'].items():
                # 查找该回忆卡的效果
                card_effect = None
                for card_data in memory_card_data:
                    if card_data['名称'] == card_name:
                        card_effect = card_data['集齐效果']
                        break

                if card_effect:
                    # 解析效果并累加，每张卡的效果独立计算
                    for _ in range(card_count):
                        if '所有展台的收入增加' in card_effect:
                            percent = float(card_effect.replace('所有展台的收入增加', '').replace('%', ''))
                            bonus['all'] += percent
                        elif '消费展区的收入增加' in card_effect:
                            percent = float(card_effect.replace('消费展区的收入增加', '').replace('%', ''))
                            bonus['消费展区'] += percent
                        elif '趣味展区的收入增加' in card_effect:
                            percent = float(card_effect.replace('趣味展区的收入增加', '').replace('%', ''))
                            bonus['趣味展区'] += percent
                        elif '纪念展区的收入增加' in card_effect:
                            percent = float(card_effect.replace('纪念展区的收入增加', '').replace('%', ''))
                            bonus['纪念展区'] += percent
                        elif '所有展会事件' in card_effect and '收入增加' in card_effect:
                            percent = float(card_effect.replace('所有展会事件（帕姆快送、来宾事件、特别来宾）的收入增加', '').replace('%', ''))
                            bonus['event'] += percent

        # 将百分比转换为倍率（例如：100% -> 2.0倍，200% -> 3.0倍）
        return {
            'all': 1.0 + bonus['all'] / 100,
            '消费展区': 1.0 + bonus['消费展区'] / 100,
            '趣味展区': 1.0 + bonus['趣味展区'] / 100,
            '纪念展区': 1.0 + bonus['纪念展区'] / 100,
            'event': 1.0 + bonus['event'] / 100
        }

    def calculate_assistant_bonus(self, assistant_in_booth, current_booth_name, all_player_booths):
        """
        计算助理的加成效果
        :param assistant_in_booth: 展台中的助理数据
        :param current_booth_name: 当前展台名称
        :param all_player_booths: 所有玩家展台数据（字典格式：{booth_name: booth_data}）
        :return: 加成倍率
        """
        bonus = 1.0

        assistant_static_info = self.get_assistant_static_details(assistant_in_booth['name'])

        if assistant_static_info:
            level = assistant_in_booth.get('level', 1)
            star = assistant_in_booth.get('star', 1)

            # 计算等级加成
            bonus *= (1 + (level - 1) * 1.0)

            # 计算星级加成
            bonus *= (1 + (star - 1) * 2.0)

            # 计算特质加成
            for trait in assistant_static_info['traits']:
                # 检查是否是羁绊效果（包含"收入增加"的特质）
                import re
                if re.match(r'(.+)收入增加(\d+)%', trait):
                    matches = re.match(r'(.+)收入增加(\d+)%', trait)
                    target_name = matches.group(1)
                    increase_percent = float(matches.group(2))

                    # 检查目标助理是否在展台中工作
                    target_found = False
                    # all_player_booths 是一个字典，需要遍历其值
                    if isinstance(all_player_booths, dict):
                        for booth_name, booth_data in all_player_booths.items():
                            if booth_data.get('unlocked') and booth_data.get('assistant') and booth_data['assistant'].get('name') == target_name:
                                target_found = True
                                break
                    else:
                        # 如果是列表格式（向后兼容）
                        for booth_data in all_player_booths:
                            if booth_data.get('unlocked') and booth_data.get('assistant') and booth_data['assistant'].get('name') == target_name:
                                target_found = True
                                break
                    # 如果目标助理在工作，应用加成
                    if target_found:
                        bonus *= (1 + increase_percent / 100)
                # 检查是否是区域加成
                elif re.match(r'(.+)展区收入增加(\d+)%', trait):
                    matches = re.match(r'(.+)展区收入增加(\d+)%', trait)
                    trait_area_name = matches.group(1)
                    increase_percent = float(matches.group(2))
                    current_booth_actual_area = self.booths[current_booth_name]['area']
                    if current_booth_actual_area == trait_area_name + "展区":
                        bonus *= (1 + increase_percent / 100)
                # 检查是否是全局加成
                elif re.match(r'所有展台收入增加(\d+)%', trait):
                    matches = re.match(r'所有展台收入增加(\d+)%', trait)
                    increase_percent = float(matches.group(1))
                    bonus *= (1 + increase_percent / 100)

        return bonus

    def get_city_level(self, total_income):
        """计算城市等级"""
        thresholds = {
            1: 0,
            2: 1e12,
            3: 1e13,
            4: 1e14,
            5: 1e15,
            6: 1e16,
            7: 1e17,
            8: 1e18,
            9: 1e19,
            10: 1e20,
        }
        level = 1
        for lv, need in thresholds.items():
            if total_income >= need:
                level = lv
        return level

    def get_city_buff(self, level):
        """计算城市加成"""
        return 1 + (level - 1) * 1.0

    def get_city_level_threshold(self, level):
        """获取城市等级阈值"""
        thresholds = {
            1: 0,
            2: 1e12,
            3: 1e13,
            4: 1e14,
            5: 1e15,
            6: 1e16,
            7: 1e17,
            8: 1e18,
            9: 1e19,
            10: 1e20,
        }
        return thresholds.get(level, 1e14)

    def calculate_reward_multiplier(self, selected_option, selected_branch):
        """计算奖励倍率"""
        # 获取当前分支的奖励等级和概率
        current_reward_level = selected_branch['奖励']
        current_probability = int(selected_branch['概率'].replace('%', ''))

        # 找出该选项中所有相同奖励等级的分支
        same_level_branches = []
        for branch in selected_option['分支']:
            if branch['奖励'] == current_reward_level:
                probability = int(branch['概率'].replace('%', ''))
                same_level_branches.append(probability)

        # 如果只有一个相同等级的分支，返回基础倍率1.0
        if len(same_level_branches) <= 1:
            return 1.0

        # 找出最低概率
        min_probability = min(same_level_branches)

        # 如果当前概率是最低的，返回基础倍率1.0
        if current_probability <= min_probability:
            return 1.0

        # 概率高的分支比概率低的分支奖励提高1.3倍
        return 1.3

    def give_event_reward(self, player, reward_level, reward_multiplier=1.0):
        """根据奖励等级发放奖励"""
        # 计算当前收入速率（用于B和A级奖励）
        current_income_rate = 0
        city_level = self.get_city_level(player['total_income'])
        buff = self.get_city_buff(city_level)
        memory_card_bonus = self.get_memory_card_bonus(player)

        for booth_name, booth_info in player['booths'].items():
            if booth_info['unlocked'] and booth_info['assistant']:
                booth_base = self.booths[booth_name]['base_income']
                assistant = booth_info['assistant']
                assistant_bonus = self.calculate_assistant_bonus(assistant, booth_name, player['booths'])
                booth_area = self.booths[booth_name]['area']
                area_bonus = memory_card_bonus.get(booth_area, 1.0)
                booth_income = self.parse_gold(booth_base) * buff * assistant_bonus * memory_card_bonus['all'] * area_bonus
                current_income_rate += booth_income

        reward_text = "未知奖励"
        if reward_level == 'B':
            # 获得当前收入*5分钟的金币
            gold_reward = int(current_income_rate * 300 * reward_multiplier)  # 5分钟 = 300秒
            player['gold'] += gold_reward
            reward_text = f"{self.format_gold(gold_reward)} 金币"
        elif reward_level == 'A':
            # 获得当前收入*10分钟的金币或者3个回忆卡抽取券（50%概率）
            if self.random.randint(1, 100) <= 50:
                gold_reward = int(current_income_rate * 600 * reward_multiplier)  # 10分钟 = 600秒
                player['gold'] += gold_reward
                reward_text = f"{self.format_gold(gold_reward)} 金币"
            else:
                ticket_reward = int(3 * reward_multiplier)
                player['memory_tickets'] += ticket_reward
                reward_text = f"{ticket_reward}张回忆卡抽取券"
        elif reward_level == 'S':
            # 获得普通邀约卡*1
            card_reward = int(1 * reward_multiplier)
            player['tickets']['普通'] += card_reward
            reward_text = f"{card_reward}张普通邀约卡"
        elif reward_level == 'SS':
            # 获得黄金邀约卡*1
            card_reward = int(1 * reward_multiplier)
            player['tickets']['黄金'] += card_reward
            reward_text = f"{card_reward}张黄金邀约卡"
        elif reward_level == 'SSS':
            # 获得炫彩邀约卡*1
            card_reward = int(1 * reward_multiplier)
            player['tickets']['炫彩'] += card_reward
            reward_text = f"{card_reward}张炫彩邀约卡"

        # 如果有奖励倍率加成，在奖励文本中显示
        if reward_multiplier > 1.0:
            reward_text += " (高概率分支奖励加成!)"

        return reward_text

    @filter.regex("^(普通|黄金|炫彩)邀约$")
    async def gacha_assistant(self, event: AstrMessageEvent):
        """助理邀约系统"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        # 匹配邀约类型
        import re
        match = re.match(r'^(普通|黄金|炫彩)邀约$', event.message_str)
        if not match:
            yield event.make_result().message("格式错误，请使用：普通邀约/黄金邀约/炫彩邀约")
            return
            
        type_name = match.group(1)
        pool = self.assistant_pool[type_name]
        
        gacha_count = 1  # 默认抽卡次数
        used_tickets_this_gacha = 0
        
        # 检查是否有邀约卡，并确定抽卡次数
        if player['tickets'][type_name] > 0:
            gacha_count = min(player['tickets'][type_name], 3)  # 最多使用3张卡
        else:
            # 检查钻石是否足够
            if player['diamond'] < pool['cost']:
                yield event.make_result().message(f"钻石不足，需要{pool['cost']}钻石\n当前钻石：{player['diamond']}")
                return
            player['diamond'] -= pool['cost']
            
        # 加载所有助理的基础数据
        assistant_data = self.load_all_assistant_data()
        if not assistant_data:
            yield event.make_result().message("助理数据加载失败，请稍后重试")
            return
            
        results = []  # 用于存储每次抽卡的结果
        
        # 计算当前总收入速率，用于邀约奖励
        current_income_rate = 0
        city_level_for_rate = self.get_city_level(player['total_income'])
        buff_for_rate = self.get_city_buff(city_level_for_rate)
        
        for booth_name, booth_info in player['booths'].items():
            if booth_info['unlocked'] and booth_info['assistant']:
                booth_base = self.parse_gold(self.booths[booth_name]['base_income'])
                assistant = booth_info['assistant']
                assistant_bonus = self.calculate_assistant_bonus(assistant, booth_name, player['booths'])
                current_income_rate += booth_base * buff_for_rate * assistant_bonus
                
        gacha_rewards_config = {
            '普通': {'gold_rate': 0.001, 'diamond': 5},  # 0.1% 金币 + 5 钻石
            '黄金': {'gold_rate': 0.005, 'diamond': 10},  # 0.5% 金币 + 10 钻石
            '炫彩': {'gold_rate': 0.01, 'diamond': 30},   # 1% 金币 + 30 钻石
        }
        
        for i in range(gacha_count):
            current_gacha_result = ""
            # 如果是使用邀约卡，则扣除
            if player['tickets'][type_name] > 0:
                player['tickets'][type_name] -= 1
                used_tickets_this_gacha += 1
            elif i > 0:  # 如果第一抽不是用卡（说明是用钻石），后续不再继续（因为钻石只够一次）
                break
                
            # 发放邀约奖励
            reward_config = gacha_rewards_config[type_name]
            gold_reward = int(current_income_rate * reward_config['gold_rate'])
            diamond_reward = reward_config['diamond']
            
            player['gold'] += gold_reward
            player['diamond'] += diamond_reward
            
            current_gacha_result += f"✨ 额外奖励：获得 {self.format_gold(gold_reward)} 金币，{diamond_reward} 钻石！\n"
            
            # 抽卡：先抽等级 (稀有度)
            import random
            rand = random.random()
            acc = 0
            assistant_rarity = '见习'  # 默认稀有度
            
            for k, v in pool['rates'].items():
                acc += v
                if rand <= acc:
                    assistant_rarity = k
                    break
                    
            # 根据等级筛选助理
            available_assistants = [a for a in assistant_data if a['level'] == assistant_rarity]
            
            if not available_assistants:
                current_gacha_result += f"第 {i + 1} 次邀约：没有找到符合条件的助理。"
                results.append(current_gacha_result)
                continue
                
            # 随机选择一个助理
            assistant = random.choice(available_assistants)
            
            # 检查是否已拥有该助理
            owned_assistant = None
            owned_assistant_index = -1
            
            for idx, pa in enumerate(player['assistants']):
                if pa['name'] == assistant['name']:
                    owned_assistant = pa
                    owned_assistant_index = idx
                    break
                    
            if owned_assistant:
                # 转换为碎片
                if assistant['name'] not in player['fragments']:
                    player['fragments'][assistant['name']] = 0
                player['fragments'][assistant['name']] += 1
                
                current_gacha_result += f"获得助理碎片：【{assistant['name']}】x1 (当前拥有 {player['fragments'][assistant['name']]} 个)"
                
                # 检查是否可以升星
                current_star = player['assistants'][owned_assistant_index]['star']
                if current_star < 4 and current_star in self.star_upgrade_cost:
                    needed_fragments = self.star_upgrade_cost[current_star]
                    if player['fragments'][assistant['name']] >= needed_fragments:
                        # 自动升星
                        player['fragments'][assistant['name']] -= needed_fragments
                        player['assistants'][owned_assistant_index]['star'] += 1
                        current_gacha_result += f"\n  🎉 恭喜！【{assistant['name']}】升到 {player['assistants'][owned_assistant_index]['star']} 星！(剩余碎片 {player['fragments'][assistant['name']]})"
                    else:
                        current_gacha_result += f" (距离升星还需 {needed_fragments - player['fragments'][assistant['name']]} 个)"
            else:
                # 新助理
                player['assistants'].append({
                    'name': assistant['name'],
                    'level': 1,  # 初始等级为1
                    'star': 1    # 初始星级为1
                })
                current_gacha_result += f"🎉 恭喜获得新助理：【{assistant['name']}】({assistant_rarity})！"
                
                # 更新新手引导步骤 (只在第一次获得助理时触发)
                if player['tutorial_step'] == 1 and len(player['assistants']) == 1:
                    player['tutorial_step'] = 2
                    current_gacha_result += f"\n\n【新手引导】\n2️⃣ 现在使用'分配助理 {assistant['name']} 咖啡馆'将助理分配到展区"
                else:
                    current_gacha_result += "\n  请使用'分配助理'命令将其分配到展区。"
                    
            results.append(current_gacha_result)
            
        reply_msg = f"✨ {type_name}邀约结果 ✨\n"
        if used_tickets_this_gacha > 0:
            reply_msg += f"本次消耗 {used_tickets_this_gacha} 张{type_name}邀约卡。\n"
        else:
            reply_msg += f"本次消耗 {pool['cost']} 钻石。\n"
        reply_msg += "--------------------\n"
        reply_msg += "\n--------------------\n".join(results)
        
        # 显示剩余资源
        reply_msg += "\n\n【剩余资源】\n"
        reply_msg += f"钻石：{player['diamond']}\n"
        reply_msg += "邀约卡：\n"
        for ticket_type, count in player['tickets'].items():
            reply_msg += f"- {ticket_type}邀约卡：{count}张\n"
            
        self.save_player(event, player)
        yield event.make_result().message(reply_msg)
        
    @filter.regex("^一键收取$")
    async def collect_all(self, event: AstrMessageEvent):
        """一键收取所有展台收益"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        now = int(time.time())
        income = 0
        city_level = self.get_city_level(player['total_income'])
        buff = self.get_city_buff(city_level)
        
        # 计算回忆卡加成
        memory_card_bonus = self.get_memory_card_bonus(player)
        
        for booth_name, info in player['booths'].items():
            if not info['unlocked'] or not info['assistant']:
                continue
                
            seconds = now - info['last_collect']
            booth_base = self.parse_gold(self.booths[booth_name]['base_income'])
            assistant = info['assistant']
            
            # 计算基础收入
            base_income = seconds * booth_base * buff
            
            # 计算助理加成
            assistant_bonus = self.calculate_assistant_bonus(assistant, booth_name, player['booths'])
            
            # 应用回忆卡加成（确保即使加成缺失也不影响总收入）
            area = self.booths[booth_name]['area']
            area_bonus = memory_card_bonus.get(area, 1.0)
            booth_income = base_income * assistant_bonus * memory_card_bonus['all'] * area_bonus
            
            income += booth_income
            info['last_collect'] = now
            
        # 应用展会事件加成
        final_income = income * memory_card_bonus.get('event', 1.0)
        player['gold'] += final_income
        player['total_income'] += final_income
        
        # 检查展会升级
        new_level = self.get_city_level(player['total_income'])
        if new_level > player['city_level']:
            player['city_level'] = new_level
            level_up_msg = f"\n🏙️ 恭喜！展会升级到Lv.{new_level}，全局收益提升至{self.get_city_buff(new_level) * 100}%！"
        else:
            level_up_msg = ''
            
        # 更新新手引导步骤
        if player['tutorial_step'] == 3:
            player['tutorial_step'] = 4
            tutorial_msg = "\n\n【新手引导完成】\n恭喜你完成了新手引导！现在你可以：\n1. 继续抽取更多助理\n2. 解锁新的展台\n3. 升级助理等级\n4. 查看'展会信息'了解更多玩法"
        else:
            tutorial_msg = ''
            
        # 先保存玩家数据，确保players表中有记录
        save_result = self.save_player(event, player)
        if not save_result:
            print(f"警告: 用户 {event.get_sender_id()} 数据保存失败，跳过排行榜更新")
        else:
            # 保存成功后更新世界排行榜
            user_id = event.get_sender_id()
            ranking_updated = self.update_world_ranking(user_id, player['name'], player['gold'], player['total_income'])
            if not ranking_updated:
                print(f"警告: 用户 {user_id} ({player['name']}) 的排行榜更新失败")
        
        msg = f'本次收取获得金币：{self.format_gold(final_income)}\n当前金币：{self.format_gold(player["gold"])}{level_up_msg}{tutorial_msg}'
        
        # 检查是否触发来宾事件（10%概率）
        event_triggered = False
        
        # 清理过期事件
        if player['current_event'] and now > player['event_expire_time']:
            player['current_event'] = None
            player['event_expire_time'] = 0
            self.save_player(event, player)
            
        # 如果没有当前事件，有10%概率触发新事件
        if not player['current_event'] and (now % 10) < 1:  # 简单的10%概率实现
            event_data = self.load_star_sea_anecdotes()
            if event_data and '星海轶闻' in event_data and event_data['星海轶闻']:
                import random
                random_event = random.choice(event_data['星海轶闻'])
                player['current_event'] = random_event
                player['event_expire_time'] = now + 3600  # 事件1小时后过期
                event_triggered = True
                self.save_player(event, player)
                
        # 如果触发了事件或有当前事件，显示提示
        if event_triggered:
            msg += "\n\n🎭 来宾事件触发！\n"
            msg += f"你遇到了来自 {player['current_event']['角色']} 的事件！\n"
            msg += "使用「查看事件」指令查看详情并做出选择。"
        elif player['current_event']:
            msg += "\n\n🎭 你有一个未处理的来宾事件\n"
            msg += "使用「查看事件」指令查看详情。"
            
        yield event.make_result().message(msg)
        yield event.stop_event()

    @filter.regex("^解锁(.*)$")
    async def unlock_booth(self, event: AstrMessageEvent):
        """解锁展台"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        # 获取要解锁的展台名称
        import re
        match = re.match(r'解锁(.*)', event.message_str)
        if not match:
            yield event.make_result().message("格式错误，请使用：解锁+展台名称")
            return
            
        booth_name = match.group(1).strip()
        
        # 检查展台是否存在
        if booth_name not in self.booths:
            yield event.make_result().message("没有这个展台")
            return
            
        # 检查展台是否已解锁
        if player['booths'][booth_name]['unlocked']:
            yield event.make_result().message("该展台已解锁")
            return
            
        # 计算解锁费用
        cost = self.parse_gold(self.booths[booth_name]['unlock_cost'])
        
        # 检查金币是否足够
        if player['gold'] < cost:
            yield event.make_result().message("金币不足，无法解锁")
            return
            
        # 扣除金币并解锁展台
        player['gold'] -= cost
        player['booths'][booth_name]['unlocked'] = True
        
        # 保存玩家数据
        self.save_player(event, player)
        
        yield event.make_result().message(f"成功解锁展台：{booth_name}！\n请分配助理到该展台以获得收益。")

    @filter.regex("^展会信息$")
    async def show_info(self, event: AstrMessageEvent):
        """显示展会信息"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        now = time.time()
        income_rate = 0
        city_level = self.get_city_level(player['total_income'])
        buff = self.get_city_buff(city_level)
        booth_details_for_display = {}
        
        # 计算回忆卡加成
        memory_card_bonus = self.get_memory_card_bonus(player)
        
        for booth, info in player['booths'].items():
            current_booth_income = 0
            if info['unlocked'] and info['assistant']:
                booth_base = self.booths[booth]['base_income']
                assistant = info['assistant']
                assistant_bonus = self.calculate_assistant_bonus(assistant, booth, player['booths'])
                
                # 计算基础收入（每秒）
                base_income = self.parse_gold(booth_base) * buff
                
                # 应用回忆卡加成
                area_bonus = memory_card_bonus.get(self.booths[booth]['area'], 1.0)
                current_booth_income = base_income * assistant_bonus * memory_card_bonus['all'] * area_bonus
                
                income_rate += current_booth_income
                
            booth_details_for_display[booth] = {'income': current_booth_income}
            
        # 应用展会事件加成到总收入速率
        income_rate *= memory_card_bonus['event']
        
        next_level = city_level + 1 if city_level < 10 else 10
        next_need = self.get_city_level_threshold(next_level)
        
        player_id = player.get('player_id', '未分配')
        msg = f"🏙️ 展会名称：{player['name']}\n"
        msg += f"🆔 玩家ID：{player_id}\n"
        msg += f"展会等级：Lv.{city_level} (收益加成：{buff * 100}%)\n"
        msg += f"金币：{self.format_gold(player['gold'])}\n"
        msg += f"钻石：{player['diamond']}\n"
        msg += f"总收入：{self.format_gold(player['total_income'])}\n"
        msg += f"当前金币获取速率：{self.format_gold(income_rate)}/秒\n"
        
        # 显示邀约卡数量（注释掉，与PHP版本保持一致）
        """
        msg += "\n【邀约卡】\n"
        for type, count in player['tickets'].items():
            msg += f"{type}邀约卡：{count}张\n"
        """
        
        if city_level < 10:
            msg += f"\n下一级展会Lv.{next_level} 需要总收入：{self.format_gold(next_need)}\n"
        else:
            msg += "\n已达最高展会等级\n"
            
        # 区域分组
        areas = {'消费展区': {}, '趣味展区': {}, '纪念展区': {}}
        for booth, info in player['booths'].items():
            area = self.booths[booth]['area']
            areas[area][booth] = info
            
        for area, booths in areas.items():
            msg += f"\n★【{area}】★\n"
            for booth, info in booths.items():
                msg += ('✅' if info['unlocked'] else '❌') + booth
                if not info['unlocked']:
                    msg += f"（解锁价：{self.booths[booth]['unlock_cost']}）"
                else:
                    booth_income_to_show = booth_details_for_display[booth]['income']
                    if booth_income_to_show > 0:
                        msg += f" (收益: {self.format_gold(booth_income_to_show)}/秒)"
                    elif info['unlocked'] and not info['assistant']:
                        msg += " (无助理)"
                        
                if info['unlocked'] and info['assistant']:
                    # 从玩家的 assistants 数组中获取助理的等级和星级
                    level = 1
                    star = 1
                    assistant_rank = '见习'
                    assistant_details = self.get_assistant_static_details(info['assistant']['name'])
                    if assistant_details:
                        assistant_rank = assistant_details['level']
                        
                    for player_assistant in player['assistants']:
                        if player_assistant['name'] == info['assistant']['name']:
                            level = player_assistant['level']
                            star = player_assistant['star']
                            break
                    msg += f" [{info['assistant']['name']}|{assistant_rank}](Lv.{level}|{star}⭐)"
                msg += "\n"
                
        # 显示助理碎片（注释掉，与PHP版本保持一致）
        """
        if player['fragments']:
            msg += "\n【助理碎片】\n"
            for name, count in player['fragments'].items():
                msg += f"{name}：{count}个\n"
        """
        
        # 显示新手引导
        if player['tutorial_step'] <= 3:
            msg += "\n【新手引导】\n"
            if player['tutorial_step'] == 1:
                msg += "1️⃣ 使用'普通邀约'来获得你的第一个助理\n"
            elif player['tutorial_step'] == 2:
                msg += "2️⃣ 使用'分配助理 助理名 咖啡馆'将助理分配到展区\n"
            elif player['tutorial_step'] == 3:
                msg += "3️⃣ 使用'一键收取'来获取收益\n"
                
        # 显示回忆卡加成
        if player.get('memory_cards'):
            msg += "\n\n✨ 回忆卡加成 ✨"
            
            # 计算并显示各类加成的总和
            all_bonus = (memory_card_bonus['all'] - 1) * 100
            consume_bonus = (memory_card_bonus['消费展区'] - 1) * 100
            fun_bonus = (memory_card_bonus['趣味展区'] - 1) * 100
            memorial_bonus = (memory_card_bonus['纪念展区'] - 1) * 100
            event_bonus = (memory_card_bonus['event'] - 1) * 100
            
            if all_bonus > 0:
                msg += f"\n- 所有展台收入增加：{all_bonus}%"
            if consume_bonus > 0:
                msg += f"\n- 消费展区收入增加：{consume_bonus}%"
            if fun_bonus > 0:
                msg += f"\n- 趣味展区收入增加：{fun_bonus}%"
            if memorial_bonus > 0:
                msg += f"\n- 纪念展区收入增加：{memorial_bonus}%"
            if event_bonus > 0:
                msg += f"\n- 展会事件收入增加：{event_bonus}%"
                
        # 检查是否触发来宾事件（10%概率）
        event_triggered = False
        
        # 清理过期事件
        if player['current_event'] and now > player['event_expire_time']:
            player['current_event'] = None
            player['event_expire_time'] = 0
            
        # 如果没有当前事件，有10%概率触发新事件
        if not player['current_event'] and (now % 10) < 1:  # 简单的10%概率实现
            event_data = self.load_star_sea_anecdotes()
            if event_data and '星海轶闻' in event_data and event_data['星海轶闻']:
                import random
                random_event = random.choice(event_data['星海轶闻'])
                player['current_event'] = random_event
                player['event_expire_time'] = now + 3600  # 事件1小时后过期
                event_triggered = True
                self.save_player(event, player)
                
        # 如果触发了事件或有当前事件，显示提示
        if event_triggered:
            msg += "\n\n🎭 来宾事件触发！\n"
            msg += f"你遇到了来自 {player['current_event']['角色']} 的事件！\n"
            msg += "使用「查看事件」指令查看详情并做出选择。"
        elif player['current_event']:
            msg += "\n\n🎭 你有一个未处理的来宾事件\n"
            msg += "使用「查看事件」指令查看详情。"
            
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^世界排行$")
    async def world_rank(self, event: AstrMessageEvent):
        """世界总收入排行榜"""
        # 加载世界排行数据
        world = self.load_world()
        
        # 对世界排行按总收入排序
        world.sort(key=lambda x: x['total_income'], reverse=True)
        
        msg = "🌏 世界总收入排行榜\n"
        i = 1
        for player in world:
            if i > 20:  # 显示前20名
                break
            msg += f"{i}. {player['name']}：{self.format_gold(player['total_income'])}\n"
            i += 1
            
        # 根据是否使用ArkReply决定回复方式
        if self.useArkReply:
            # 这里可以实现ArkReply的回复方式，但由于Python版本可能不支持，暂时使用普通回复
            yield event.make_result().message(msg)
        else:
            yield event.make_result().message(msg)
        yield event.stop_event()
            
    @filter.regex("^玩家[Ii][Dd]$")
    async def show_my_player_id(self, event: AstrMessageEvent):
        """显示玩家ID信息"""
        # 加载玩家数据
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("你还没有创建展会，请使用 \"创建展会 你的展会名\" 来开始游戏")
            return
        
        name = player['name']
        player_id = player.get('player_id', '未分配')
        
        msg = "🆔 你的玩家信息"
        msg = "🆔 你的玩家信息\n"
        msg += f"展会名称：{name}\n"
        msg += f"玩家ID：{player_id}\n"
        msg += "💡 玩家ID可用于添加好友等功能"
        
        # 根据是否使用ArkReply决定回复方式
        if self.useArkReply:
            # 这里可以实现ArkReply的回复方式，但由于Python版本可能不支持，暂时使用普通回复
            yield event.make_result().message(msg)
        else:
            yield event.make_result().message(msg)
        yield event.stop_event()
            
    @filter.regex("^改名(.*)$")
    async def change_name(self, event: AstrMessageEvent):
        """修改展会名称"""
        # 加载玩家数据
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("你还没有创建展会，请使用 \"创建展会 你的展会名\" 来开始游戏")
            return
        
        # 获取新名称
        new_name = event.message_str.replace("改名", "").strip()
        if not new_name:
            yield event.make_result().message(f"请输入新的展会名称，格式：改名 新名称\n\n💎 改名费用：100钻石\n当前钻石：{player['diamond']}")
            return
        # 检查名称长度限制
        if len(new_name) > 20:
            yield event.make_result().message("展会名称过长，请使用20个字符以内的名称")
            return
        
        # 检查名称是否包含敏感词
        if self.contains_banned_words(new_name):
            yield event.make_result().message("展会名称包含不当内容，请更换一个合适的名称")
            return
        
        # 检查名称是否包含特殊字符
        import re
        if re.search(r'[<>\"\\\'/]', new_name):
            yield event.make_result().message("展会名称不能包含特殊字符，请重新输入")
            return
        
        # 检查是否与当前名称相同
        if new_name == player['name']:
            yield event.make_result().message("新名称与当前名称相同，无需改名")
            return
        
        # 检查重名
        if self.check_name_exists(new_name):
            yield event.make_result().message(f"展会名称「{new_name}」已被占用，请更换另一个名字")
            return
        # 检查钻石是否足够
        if player['diamond'] < 100:
            yield event.make_result().message(f"钻石不足，改名需要100钻石\n当前钻石：{player['diamond']}")
            return
        
        # 执行改名
        old_name = player['name']
        player['name'] = new_name
        player['diamond'] -= 100
        
        # 保存玩家数据
        self.save_player(event, player)
        
        # 更新世界排行榜
        try:
            user_id = event.get_sender_id()
            self.update_world_ranking(user_id, player['name'], player['gold'], player['total_income'])
        except Exception as e:
            logger.error(f"更新排行榜失败: {str(e)}")
        
        # 返回结果
        msg = f"🎉 改名成功！\n\n旧名称：{old_name}\n新名称：{new_name}\n\n💎 消耗钻石：100\n剩余钻石：{player['diamond']}"
        
        # 根据是否使用ArkReply决定回复方式
        if self.useArkReply:
            # 这里可以实现ArkReply的回复方式，但由于Python版本可能不支持，暂时使用普通回复
            yield event.make_result().message(msg)
        else:
            yield event.make_result().message(msg)
        yield event.stop_event()
    
    @filter.regex("^助理卡池$")
    async def show_gacha_info(self, event: AstrMessageEvent):
        """显示助理卡池信息"""
        msg = "【助理卡池消耗与概率】\n"
        for type_name, pool in self.assistant_pool.items():
            msg += f"{type_name}卡池：{pool['cost']}钻石/次\n"
            msg += f"  资深：{int(pool['rates']['资深'] * 100)}%\n"
            msg += f"  熟练：{int(pool['rates']['熟练'] * 100)}%\n"
            msg += f"  见习：{int(pool['rates']['见习'] * 100)}%\n"
        
        msg += "\n【升星所需碎片】\n"
        msg += "1星→2星：3个碎片\n"
        msg += "2星→3星：10个碎片\n"
        msg += "3星→4星：20个碎片\n"
        
        msg += "\n注：获得重复助理会自动转化为碎片，碎片足够时会自动升星！"
        
        # 根据是否使用ArkReply决定回复方式
        if self.useArkReply:
            # 这里可以实现ArkReply的回复方式，但由于Python版本可能不支持，暂时使用普通回复
            yield event.make_result().message(msg)
        else:
            yield event.make_result().message(msg)
        yield event.stop_event()
            
    @filter.regex("^展会指令$")
    async def show_cmds(self, event: AstrMessageEvent):
        """展会指令列表"""
        msg = "【指令列表】\n"
        msg += "⭐\n"

        # 无需参数的指令
        msg += "【基础指令】\n"
        msg += "展会信息 | 一键收取 | 我的助理\n"
        msg += "世界排行 | 展会签到 | 助理卡池\n"
        msg += "我的背包 | 我的回忆卡 | 我的ID\n"
        msg += "一键升级助理\n"

        msg += "\n【邀约指令】\n"
        msg += "普通邀约 | 黄金邀约 | 炫彩邀约\n"
        msg += "\n【回忆卡指令】\n"
        msg += "抽取回忆1/2/3/4\n"
        msg += "\n【来宾事件指令】\n"
        msg += "查看事件 | 事件选择+数字\n"

        msg += "\n⭐\n"

        # 需要参数的指令(每行一个)
        msg += "【需要参数的指令】\n"
        msg += "创建展会 展会名\n"
        msg += "改名 新名称 (消耗100钻石)\n"
        msg += "分配助理 助理名 展台\n"
        msg += "查看展台 展台名\n"
        msg += "升级助理 助理名\n"
        msg += "快速升级 助理名\n"
        msg += "解锁 展台名\n"

        msg += "⭐\n"
        msg += "参数说明：使用空格分隔参数，例如：'分配助理 助理名 咖啡馆'\n"
        
        # 根据是否使用ArkReply决定回复方式
        if self.useArkReply:
            # 这里可以实现ArkReply的回复方式，但由于Python版本可能不支持，暂时使用普通回复
            yield event.make_result().message(msg)
        else:
            yield event.make_result().message(msg)
        yield event.stop_event()
    
    @filter.regex("^我的助理$")
    async def show_assistants(self, event: AstrMessageEvent):
        """显示我的助理列表"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        if not player['assistants']:
            yield event.make_result().message("你还没有任何助理，使用'普通邀约'来获得你的第一个助理")
            return
            
        msg = "🧑‍💼 我的助理列表\n"
        msg += "格式：助理名 | 等级 | 星级 | 工作状态\n"
        msg += "--------------------\n"
        
        for assistant in player['assistants']:
            name = assistant['name']
            level = assistant['level']
            star = assistant['star']
            
            # 查找助理的工作状态
            working_at = "空闲"
            for booth_name, booth_info in player['booths'].items():
                if booth_info['unlocked'] and booth_info['assistant'] and booth_info['assistant']['name'] == name:
                    working_at = f"工作于{booth_name}"
                    break
                    
            msg += f"{name} | Lv.{level} | {star}⭐ | {working_at}\n"
            
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^升级助理(.*)$")
    async def upgrade_assistant(self, event: AstrMessageEvent):
        """升级助理等级"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        # 获取助理名称
        assistant_name = event.message_str.replace("升级助理", "").strip()
        if not assistant_name:
            yield event.make_result().message("格式错误，请使用：升级助理 助理名")
            return
            
        # 查找助理
        assistant_index = -1
        for i, assistant in enumerate(player['assistants']):
            if assistant['name'] == assistant_name:
                assistant_index = i
                break
                
        if assistant_index == -1:
            yield event.make_result().message(f"未找到助理：{assistant_name}")
            return
            
        assistant = player['assistants'][assistant_index]
        current_level = assistant['level']
        
        # 计算升级费用
        upgrade_cost = int(self.level_upgrade_base_cost * (self.level_upgrade_multiplier ** (current_level - 1)))
        
        # 检查金币是否足够
        if player['gold'] < upgrade_cost:
            yield event.make_result().message(f"金币不足，升级需要 {self.format_gold(upgrade_cost)} 金币\n当前金币：{self.format_gold(player['gold'])}")
            return
            
        # 执行升级
        player['gold'] -= upgrade_cost
        player['assistants'][assistant_index]['level'] += 1
        
        # 保存玩家数据
        self.save_player(event, player)
        
        msg = f"🎉 升级成功！\n"
        msg += f"助理：{assistant_name}\n"
        msg += f"等级：Lv.{current_level} → Lv.{current_level + 1}\n"
        msg += f"消耗金币：{self.format_gold(upgrade_cost)}\n"
        msg += f"剩余金币：{self.format_gold(player['gold'])}"
        
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^快速升级(.*)$")
    async def quick_upgrade_assistant(self, event: AstrMessageEvent):
        """快速升级助理（升级10级）"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        # 获取助理名称
        assistant_name = event.message_str.replace("快速升级", "").strip()
        if not assistant_name:
            yield event.make_result().message("格式错误，请使用：快速升级 助理名")
            return
            
        # 查找助理
        assistant_index = -1
        for i, assistant in enumerate(player['assistants']):
            if assistant['name'] == assistant_name:
                assistant_index = i
                break
                
        if assistant_index == -1:
            yield event.make_result().message(f"未找到助理：{assistant_name}")
            return
            
        assistant = player['assistants'][assistant_index]
        current_level = assistant['level']
        
        # 计算升级10级的总费用
        total_cost = 0
        for i in range(10):
            level_cost = int(self.level_upgrade_base_cost * (self.level_upgrade_multiplier ** (current_level + i - 1)))
            total_cost += level_cost
            
        # 检查金币是否足够
        if player['gold'] < total_cost:
            yield event.make_result().message(f"金币不足，快速升级10级需要 {self.format_gold(total_cost)} 金币\n当前金币：{self.format_gold(player['gold'])}")
            return
            
        # 执行升级
        player['gold'] -= total_cost
        player['assistants'][assistant_index]['level'] += 10
        
        # 保存玩家数据
        self.save_player(event, player)
        
        msg = f"🎉 快速升级成功！\n"
        msg += f"助理：{assistant_name}\n"
        msg += f"等级：Lv.{current_level} → Lv.{current_level + 10}\n"
        msg += f"消耗金币：{self.format_gold(total_cost)}\n"
        msg += f"剩余金币：{self.format_gold(player['gold'])}"
        
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^分配助理(.*)$")
    async def assign_assistant(self, event: AstrMessageEvent):
        """分配助理到展台"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        # 解析命令参数
        import re
        text = event.message_str.replace("分配助理", "").strip()
        if not text:
            yield event.make_result().message("格式错误，请使用：分配助理 助理名 展台名")
            return
            
        # 尝试分割参数
        parts = text.split()
        if len(parts) < 2:
            yield event.make_result().message("格式错误，请使用：分配助理 助理名 展台名")
            return
            
        assistant_name = parts[0]
        booth_name = " ".join(parts[1:])  # 支持展台名包含空格
        
        # 检查助理是否存在
        assistant_found = None
        for assistant in player['assistants']:
            if assistant['name'] == assistant_name:
                assistant_found = assistant
                break
                
        if not assistant_found:
            yield event.make_result().message(f"未找到助理：{assistant_name}")
            return
            
        # 检查展台是否存在
        if booth_name not in player['booths']:
            yield event.make_result().message(f"展台不存在：{booth_name}")
            return
            
        # 检查展台是否已解锁
        if not player['booths'][booth_name]['unlocked']:
            yield event.make_result().message(f"展台未解锁：{booth_name}")
            return
            
        # 检查助理是否已经在工作
        current_booth = None
        for booth, info in player['booths'].items():
            if info['assistant'] and info['assistant']['name'] == assistant_name:
                current_booth = booth
                break
                
        # 检查目标展台是否已有助理
        if player['booths'][booth_name]['assistant']:
            current_assistant = player['booths'][booth_name]['assistant']['name']
            yield event.make_result().message(f"展台 {booth_name} 已有助理 {current_assistant}，请先移除或重新分配")
            return
            
        # 执行分配
        if current_booth:
            player['booths'][current_booth]['assistant'] = None
            
        player['booths'][booth_name]['assistant'] = assistant_found.copy()
        player['booths'][booth_name]['last_collect'] = int(time.time())
        
        # 更新新手引导步骤
        if player['tutorial_step'] == 2:
            player['tutorial_step'] = 3
            tutorial_msg = "\n\n【新手引导】\n3️⃣ 现在使用'一键收取'来获取收益"
        else:
            tutorial_msg = ""
            
        # 保存玩家数据
        self.save_player(event, player)
        
        msg = f"✅ 分配成功！\n"
        msg += f"助理 {assistant_name} 已分配到 {booth_name}{tutorial_msg}"
        
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^一键升级助理$")
    async def bulk_upgrade_assistants(self, event: AstrMessageEvent):
        """一键升级所有助理"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        if not player['assistants']:
            yield event.make_result().message("你还没有任何助理")
            return
            
        # 计算所有助理升级1级的总费用
        total_cost = 0
        upgrade_details = []
        
        for assistant in player['assistants']:
            current_level = assistant['level']
            upgrade_cost = int(self.level_upgrade_base_cost * (self.level_upgrade_multiplier ** (current_level - 1)))
            total_cost += upgrade_cost
            upgrade_details.append({
                'name': assistant['name'],
                'cost': upgrade_cost,
                'from_level': current_level,
                'to_level': current_level + 1
            })
            
        # 检查金币是否足够
        if player['gold'] < total_cost:
            yield event.make_result().message(f"金币不足，升级所有助理需要 {self.format_gold(total_cost)} 金币\n当前金币：{self.format_gold(player['gold'])}")
            return
            
        # 执行升级
        player['gold'] -= total_cost
        for assistant in player['assistants']:
            assistant['level'] += 1
            
        # 保存玩家数据
        self.save_player(event, player)
        
        msg = f"🎉 一键升级完成！\n"
        msg += f"升级了 {len(player['assistants'])} 个助理\n"
        msg += f"总消耗金币：{self.format_gold(total_cost)}\n"
        msg += f"剩余金币：{self.format_gold(player['gold'])}"
        
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^展会签到$")
    async def daily_check_in(self, event: AstrMessageEvent):
        """每日签到"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        import datetime
        today = datetime.date.today().isoformat()
        
        # 检查是否已签到
        if player.get('last_checkin_date') == today:
            yield event.make_result().message(f"{player['name']}，你今天已经签到过了，明天再来吧！\n当前钻石：{player['diamond']}")
            return
            
        # 初始化连续签到计数器
        if 'consecutive_checkins' not in player:
            player['consecutive_checkins'] = 0
            
        # 检查是否连续签到
        is_consecutive = False
        if player.get('last_checkin_date'):
            last_date = datetime.date.fromisoformat(player['last_checkin_date'])
            current_date = datetime.date.today()
            diff_days = (current_date - last_date).days
            is_consecutive = (diff_days == 1)
            
        # 更新连续签到计数器
        if is_consecutive:
            player['consecutive_checkins'] += 1
        else:
            player['consecutive_checkins'] = 1
            
        player['last_checkin_date'] = today
        
        # 计算奖励
        base_reward = 100
        extra_reward = 0
        
        if player['consecutive_checkins'] >= 30:
            extra_reward = 500
        elif player['consecutive_checkins'] >= 14:
            extra_reward = 300
        elif player['consecutive_checkins'] >= 7:
            extra_reward = 200
        elif player['consecutive_checkins'] >= 3:
            extra_reward = 100
            
        total_reward = base_reward + extra_reward
        player['diamond'] += total_reward
        
        # 保存玩家数据
        self.save_player(event, player)
        
        msg = f"🎉 签到成功！\n{player['name']} 获得了 {total_reward} 钻石"
        if extra_reward > 0:
            msg += f" (基础{base_reward} + 连续签到奖励{extra_reward})"
        msg += f"\n当前钻石：{player['diamond']}\n"
        msg += f"已连续签到 {player['consecutive_checkins']} 天"
        
        # 特殊里程碑提示
        if player['consecutive_checkins'] == 3:
            msg += "\n🎊 达成3天连续签到，额外获得100钻石！"
        elif player['consecutive_checkins'] == 7:
            msg += "\n🎊 达成7天连续签到，额外获得200钻石！"
        elif player['consecutive_checkins'] == 14:
            msg += "\n🎊 达成14天连续签到，额外获得300钻石！"
        elif player['consecutive_checkins'] == 30:
            msg += "\n🎊 达成30天连续签到，额外获得500钻石！"
            
        msg += "\n明天记得再来哦！"
        
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^我的背包$")
    async def show_my_bag(self, event: AstrMessageEvent):
        """显示背包信息"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        msg = "🎒 我的背包\n"
        msg += "--------------------\n"
        
        # 显示基础资源
        msg += f"💰 金币：{self.format_gold(player['gold'])}\n"
        msg += f"💎 钻石：{player['diamond']}\n"
        
        # 显示邀约卡
        msg += "\n【邀约卡】\n"
        for ticket_type, count in player['tickets'].items():
            msg += f"- {ticket_type}邀约卡：{count} 张\n"
            
        # 显示助理碎片
        if player.get('fragments'):
            msg += "\n【助理碎片】\n"
            for name, count in player['fragments'].items():
                msg += f"- {name}：{count} 个\n"
                
        # 显示回忆卡抽取券
        if player.get('memory_tickets', 0) > 0:
            msg += f"\n【回忆卡抽取券】\n"
            msg += f"- 抽取券：{player['memory_tickets']} 张\n"
            
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^我的回忆卡(.*)$")
    async def show_my_memory_cards(self, event: AstrMessageEvent):
        """显示我的回忆卡"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        # 解析区域参数
        import re
        area_index = None
        if re.match(r'^我的回忆卡(\d+)$', event.message_str):
            area_index = int(re.match(r'^我的回忆卡(\d+)$', event.message_str).group(1))
            
        area_names = {
            1: '空间站「黑塔」',
            2: '雅利洛-Ⅵ',
            3: '仙舟「罗浮」',
            4: '匹诺康尼'
        }
        
        memory_cards = self.load_memory_card_data()
        msg = "📚 回忆卡收集情况 📚\n\n"
        
        if area_index is not None and area_index in area_names:
            # 显示特定区域
            area_name = area_names[area_index]
            area_cards = [card for card in memory_cards if card['所属'] == area_name]
            
            msg += f"【{area_name}】\n"
            for card in area_cards:
                card_name = card['名称']
                has_a = '✅' if f"{card_name}_A" in player.get('memory_parts', {}) else '❌'
                has_b = '✅' if f"{card_name}_B" in player.get('memory_parts', {}) else '❌'
                has_c = '✅' if f"{card_name}_C" in player.get('memory_parts', {}) else '❌'
                completed = '🌟' if card_name in player.get('memory_cards', {}) else ''
                
                msg += f"● {card_name} {completed} [A{has_a} B{has_b} C{has_c}]\n"
                msg += f"➤ {card['介绍']}\n"
                
            # 显示已激活的效果
            if player.get('memory_cards', {}):
                msg += "✨ 已激活的集齐效果 ✨\n"
                
                # 显示每张回忆卡的效果和数量
                for card_name, card_count in player.get('memory_cards', {}).items():
                    # 查找该回忆卡的效果
                    for card_data in memory_cards:
                        if card_data['名称'] == card_name:
                            msg += f"- {card_data['集齐效果']} (拥有{card_count}张)\n"
                            break
            
            # 提示其他区域
            other_areas = []
            for idx, name in area_names.items():
                if idx != area_index:
                    other_areas.append(f"我的回忆卡{idx}")
            msg += "\n可使用指令查看其他区域：" + "、".join(other_areas)
        else:
            # 显示所有区域概括
            msg += "【所有区域概括】\n"
            for idx, area_name in area_names.items():
                area_cards = [card for card in memory_cards if card['所属'] == area_name]
                total_cards = len(area_cards)
                collected_cards = sum(1 for card in area_cards if card['名称'] in player.get('memory_cards', {}))
                
                msg += f"- {area_name}: {collected_cards}/{total_cards}\n"
            
            msg += "\n可使用指令查看具体区域：我的回忆卡1/2/3/4"
        
        # 显示回忆卡抽取券数量
        memory_tickets = player.get('memory_tickets', 0)
        msg += f"\n\n回忆卡抽取券：{memory_tickets}张"
        
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^抽取回忆(.*)$")
    async def gacha_memory_card(self, event: AstrMessageEvent):
        """抽取回忆卡"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
        
        # 检查指令格式
        import re
        match = re.match(r'^抽取回忆([1-4])$', event.message_str)
        if not match:
            yield event.make_result().message("格式错误，请使用指令：抽取回忆1/2/3/4")
            return
            
        # 获取区域信息
        area_index = int(match.group(1))
        area_names = {
            1: '空间站「黑塔」',
            2: '雅利洛-Ⅵ',
            3: '仙舟「罗浮」',
            4: '匹诺康尼'
        }
        area_name = area_names.get(area_index, '')
        
        # 检查消耗方式
        use_ticket = False
        if player.get('memory_tickets', 0) > 0:
            player['memory_tickets'] -= 1
            use_ticket = True
        else:
            # 检查钻石是否足够
            cost = 100
            if player.get('diamond', 0) < cost:
                yield event.make_result().message(f"钻石不足，需要{cost}钻石\n当前钻石：{player.get('diamond', 0)}")
                return
            player['diamond'] -= cost
        
        # 加载回忆卡数据
        memory_cards = self.load_memory_card_data()
        if not memory_cards:
            yield event.make_result().message("回忆卡数据加载失败，请稍后重试")
            return
            
        # 筛选指定区域的回忆卡
        area_cards = [card for card in memory_cards if card.get('所属') == area_name]
        if not area_cards:
            yield event.make_result().message(f"没有找到{area_name}的回忆卡数据")
            return
            
        # 按稀有度分组
        normal_cards = [card for card in area_cards if card.get('稀有度') != '稀有']
        rare_cards = [card for card in area_cards if card.get('稀有度') == '稀有']
        
        # 抽取回忆卡 (普通70%，稀有30%)
        import random
        rand = random.randint(1, 100)
        selected_pool = rare_cards if (rand <= 30 and rare_cards) else normal_cards
        if not selected_pool:
            selected_pool = normal_cards
            
        # 随机选择一张回忆卡
        selected_card = random.choice(selected_pool)
        card_name = selected_card['名称']
        
        # 随机选择部分 (A/B/C)
        parts = ['A', 'B', 'C']
        selected_part = random.choice(parts)
        part_key = f"{card_name}_{selected_part}"
        
        # 更新玩家数据
        if 'memory_parts' not in player:
            player['memory_parts'] = {}
        if part_key not in player['memory_parts']:
            player['memory_parts'][part_key] = 0
        player['memory_parts'][part_key] += 1
        
        # 检查是否可以合成完整回忆卡
        can_combine = True
        for part in parts:
            check_key = f"{card_name}_{part}"
            if not player['memory_parts'].get(check_key, 0):
                can_combine = False
                break
                
        # 构建回复消息
        msg = "✨ 回忆卡抽取结果 ✨\n"
        msg += f"区域：{area_name}\n"
        if use_ticket:
            msg += "消耗：1张回忆卡抽取券\n"
        else:
            msg += "消耗：100钻石\n"
        msg += f"获得：{card_name} {selected_part}部分\n"
        msg += f"稀有度：{selected_card.get('稀有度', '普通')}\n"
        msg += f"{selected_card.get('介绍', '')}\n"
        
        # 显示当前拥有的部分
        part_a = player['memory_parts'].get(f"{card_name}_A", 0)
        part_b = player['memory_parts'].get(f"{card_name}_B", 0)
        part_c = player['memory_parts'].get(f"{card_name}_C", 0)
        msg += f"当前拥有：{card_name} A:{part_a} B:{part_b} C:{part_c}\n"
        
        # 如果可以合成
        if can_combine:
            # 合成完整回忆卡
            for part in parts:
                part_key = f"{card_name}_{part}"
                player['memory_parts'][part_key] -= 1
                if player['memory_parts'][part_key] <= 0:
                    player['memory_parts'].pop(part_key, None)
                    
            # 添加完整回忆卡
            if 'memory_cards' not in player:
                player['memory_cards'] = {}
            if card_name not in player['memory_cards']:
                player['memory_cards'][card_name] = 0
            player['memory_cards'][card_name] += 1
            
            msg += f"\n🎉 恭喜！集齐了{card_name}的所有部分，已合成完整回忆卡！\n"
            msg += f"激活效果：{selected_card.get('集齐效果', '')}\n"
            msg += f"当前拥有该回忆卡数量：{player['memory_cards'][card_name]}张"
            
        # 保存玩家数据
        self.save_player(event, player)
        
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^查看事件$")
    async def show_current_event(self, event: AstrMessageEvent):
        """查看当前来宾事件"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        current_event = player.get('current_event')
        if not current_event:
            yield event.make_result().message("当前没有来宾事件")
            return
            
        # 检查事件是否过期
        import time
        now = int(time.time())
        if now > player.get('event_expire_time', 0):
            player['current_event'] = None
            player['event_expire_time'] = 0
            self.save_player(event, player)
            yield event.make_result().message("来宾事件已过期")
            return
            
        msg = f"🎭 来宾事件\n"
        msg += f"来宾：{current_event['角色']}\n"
        msg += f"事件：{current_event['事件']}\n\n"
        
        # 显示选项
        for i, option in enumerate(current_event['选项'], 1):
            msg += f"{i}. {option['选择']}\n"
            
        msg += "\n使用 '事件选择+数字' 来做出选择（如：事件选择1）"
        
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^事件选择(\d+)$")
    async def select_event_option(self, event: AstrMessageEvent):
        """选择事件选项"""
        # 检查玩家是否存在
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return
            
        current_event = player.get('current_event')
        if not current_event:
            yield event.make_result().message("当前没有来宾事件")
            return
            
        # 检查事件是否过期
        import time
        now = int(time.time())
        if now > player.get('event_expire_time', 0):
            player['current_event'] = None
            player['event_expire_time'] = 0
            self.save_player(event, player)
            yield event.make_result().message("来宾事件已过期")
            return
            
        # 获取选择的选项
        import re
        match = re.match(r'^事件选择(\d+)$', event.message_str)
        if not match:
            yield event.make_result().message("格式错误，请使用：事件选择+数字")
            return
            
        option_num = int(match.group(1))
        if option_num < 1 or option_num > len(current_event['选项']):
            yield event.make_result().message(f"选项不存在，请选择1-{len(current_event['选项'])}")
            return
            
        selected_option = current_event['选项'][option_num - 1]
        
        # 随机选择一个分支
        import random
        total_probability = sum(int(branch['概率'].replace('%', '')) for branch in selected_option['分支'])
        rand = random.randint(1, total_probability)
        
        acc = 0
        selected_branch = None
        for branch in selected_option['分支']:
            acc += int(branch['概率'].replace('%', ''))
            if rand <= acc:
                selected_branch = branch
                break
                
        if not selected_branch:
            yield event.make_result().message("事件处理出错")
            return
            
        # 计算奖励倍率
        reward_multiplier = self.calculate_reward_multiplier(selected_option, selected_branch)
        
        # 发放奖励
        reward_text = self.give_event_reward(player, selected_branch['奖励'], reward_multiplier)
        
        # 清除事件
        player['current_event'] = None
        player['event_expire_time'] = 0
        
        # 保存玩家数据
        self.save_player(event, player)
        
        msg = f"🎭 事件结果\n"
        msg += f"你选择了：{selected_option['选择']}\n"
        msg += f"结果：{selected_branch['结果']}\n"
        msg += f"奖励：{reward_text}"
        
        yield event.make_result().message(msg)
        yield event.stop_event()
        
    @filter.regex("^查看展台(.*)$")
    async def show_shop_detail(self, event: AstrMessageEvent):
        """显示展台详细信息"""
        # 加载玩家数据
        player = self.load_player(event)
        if not player:
            yield event.make_result().message("请先使用\"创建展会+名字\"创建展会")
            return

        # 从正则匹配中提取展台名
        booth = event.message_str.replace("查看展台", "").strip()
        if not booth:
            yield event.make_result().message("格式错误，请使用：查看展台 展台名")
            return

        # 检查展台是否存在
        if booth not in player['booths']:
            yield event.make_result().message("没有这个展台")
            return

        # 检查展台是否已解锁
        if not player['booths'][booth]['unlocked']:
            yield event.make_result().message("该展台未解锁")
            return

        # 获取展台中的助理信息
        assistant = player['booths'][booth]['assistant']
        if not assistant:
            yield event.make_result().message(f"展台：{booth}\n当前无助理")
            return

        # 获取助理的静态信息
        assistant_static_info = self.get_assistant_static_details(assistant['name'])

        # 计算升级费用
        upgrade_cost = self.level_upgrade_base_cost * (self.level_upgrade_multiplier ** (assistant['level'] - 1))

        # 计算当前速率
        city_level = self.get_city_level(player['total_income'])
        buff = self.get_city_buff(city_level)
        booth_base = self.booths[booth]['base_income']
        current_bonus = self.calculate_assistant_bonus(assistant, booth, player['booths'])
        current_rate = self.parse_gold(booth_base) * buff * current_bonus

        # 计算下一级速率
        next_level_assistant = assistant.copy()
        next_level_assistant['level'] += 1
        next_level_bonus = self.calculate_assistant_bonus(next_level_assistant, booth, player['booths'])
        next_level_rate = self.parse_gold(booth_base) * buff * next_level_bonus

        # 计算下10级速率
        next_10_level_assistant = assistant.copy()
        next_10_level_assistant['level'] += 10
        next_10_level_bonus = self.calculate_assistant_bonus(next_10_level_assistant, booth, player['booths'])
        next_10_level_rate = self.parse_gold(booth_base) * buff * next_10_level_bonus

        # 构建消息
        msg = f"🏪 展台：{booth}\n"
        msg += f"助理：{assistant['name']}\n"
        msg += f"等级：{assistant['level']}\n"
        msg += f"星级：{assistant['star']}\n"
        msg += f"升级费用：{self.format_gold(upgrade_cost)}\n\n"

        msg += "【收益速率】\n"
        msg += f"当前速率：{self.format_gold(current_rate)}/秒\n"
        msg += f"下一级速率：{self.format_gold(next_level_rate)}/秒\n"
        msg += f"下10级速率：{self.format_gold(next_10_level_rate)}/秒\n"

        # 添加特质信息
        if assistant_static_info:
            msg += "\n【特质】\n"
            for trait in assistant_static_info['traits']:
                msg += f"- {trait}\n"

            # 添加羁绊信息
            if 'bond' in assistant_static_info and assistant_static_info['bond']:
                msg += "\n【羁绊】\n"
                for bond in assistant_static_info['bond']:
                    has_bond = "❌"
                    # 检查所有展台分配的助理
                    for booth_info in player['booths'].values():
                        if booth_info['assistant'] and booth_info['assistant']['name'] == bond:
                            has_bond = "✅"
                            break
                    msg += f"- {bond} {has_bond}\n"

        # 根据是否使用ArkReply决定回复方式
        if self.useArkReply:
            # 这里可以实现ArkReply的回复方式，但由于Python版本可能不支持，暂时使用普通回复
            yield event.make_result().message(msg)
        else:
            yield event.make_result().message(msg)
        yield event.stop_event()

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        # 在initialize方法中也可以定义或修改实例变量
        self.is_initialized = True
        logger.info(f"{self.plugin_name} v{self.version} 已初始化")
    