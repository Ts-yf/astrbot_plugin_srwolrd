import pymysql
import json
import threading
import time
import queue
from contextlib import contextmanager


class ConnectionPool:
    """数据库连接池"""
    
    def __init__(self, host, port, user, password, database, charset='utf8mb4', 
                 pool_size=10, max_overflow=20, recycle=3600):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.charset = charset
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.recycle = recycle
        
        self._pool = queue.Queue(maxsize=pool_size + max_overflow)
        self._created_connections = 0
        self._lock = threading.RLock()
        
        # 预创建连接
        self._initialize_pool()
    
    def _initialize_pool(self):
        """初始化连接池"""
        for _ in range(self.pool_size):
            conn = self._create_connection()
            if conn:
                self._pool.put((conn, time.time()))
    
    def _create_connection(self):
        """创建新的数据库连接"""
        try:
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                autocommit=False
            )
            with self._lock:
                self._created_connections += 1
            return conn
        except Exception as e:
            print(f"创建数据库连接失败: {e}")
            return None
    
    def _is_connection_alive(self, conn):
        """检查连接是否存活"""
        try:
            conn.ping(reconnect=False)
            return True
        except:
            return False
    
    def get_connection(self):
        """从连接池获取连接"""
        try:
            # 尝试从池中获取连接
            while True:
                try:
                    conn, created_time = self._pool.get_nowait()
                    
                    # 检查连接是否过期
                    if time.time() - created_time > self.recycle:
                        try:
                            conn.close()
                        except:
                            pass
                        with self._lock:
                            self._created_connections -= 1
                        continue
                    
                    # 检查连接是否存活
                    if self._is_connection_alive(conn):
                        return conn
                    else:
                        try:
                            conn.close()
                        except:
                            pass
                        with self._lock:
                            self._created_connections -= 1
                        continue
                        
                except queue.Empty:
                    break
            
            # 池中没有可用连接，创建新连接
            with self._lock:
                if self._created_connections < self.pool_size + self.max_overflow:
                    conn = self._create_connection()
                    if conn:
                        return conn
            
            # 无法创建新连接，等待其他连接归还
            conn, _ = self._pool.get(timeout=30)
            if self._is_connection_alive(conn):
                return conn
            else:
                try:
                    conn.close()
                except:
                    pass
                with self._lock:
                    self._created_connections -= 1
                raise Exception("无法获取有效的数据库连接")
                
        except Exception as e:
            print(f"获取数据库连接失败: {e}")
            raise
    
    def return_connection(self, conn):
        """归还连接到连接池"""
        if conn and self._is_connection_alive(conn):
            try:
                # 重置连接状态
                conn.rollback()
                self._pool.put((conn, time.time()), timeout=1)
            except queue.Full:
                # 池已满，关闭连接
                try:
                    conn.close()
                except:
                    pass
                with self._lock:
                    self._created_connections -= 1
            except Exception as e:
                print(f"归还连接失败: {e}")
                try:
                    conn.close()
                except:
                    pass
                with self._lock:
                    self._created_connections -= 1
        else:
            # 连接无效，关闭并减少计数
            try:
                if conn:
                    conn.close()
            except:
                pass
            with self._lock:
                self._created_connections -= 1
    
    def close_all(self):
        """关闭所有连接"""
        while True:
            try:
                conn, _ = self._pool.get_nowait()
                try:
                    conn.close()
                except:
                    pass
            except queue.Empty:
                break
        
        with self._lock:
            self._created_connections = 0


class IdleTycoonDatabase:
    _instance = None
    _pool = None

    # 数据库配置
    DB_HOST = '127.0.0.1'
    DB_PORT = 3306
    DB_NAME = 'wolrd'
    DB_USER = 'wolrd'
    DB_PASS = '<PASSWORD>'

    def __init__(self):
        if IdleTycoonDatabase._pool is None:
            IdleTycoonDatabase._pool = ConnectionPool(
                host=self.DB_HOST,
                port=self.DB_PORT,
                user=self.DB_USER,
                password=self.DB_PASS,
                database=self.DB_NAME,
                charset='utf8mb4',
                pool_size=10,
                max_overflow=20,
                recycle=3600
            )
            # 连接池创建后自动创建数据库表
            try:
                self.create_tables()
                print("数据库表初始化完成")
            except Exception as e:
                print(f"数据库表初始化失败: {e}")
                # 不抛出异常，允许程序继续运行

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @contextmanager
    def cursor(self):
        """获取数据库游标的上下文管理器"""
        conn = None
        cur = None
        try:
            conn = self._pool.get_connection()
            cur = conn.cursor()
            yield cur
        finally:
            if cur:
                cur.close()
            if conn:
                self._pool.return_connection(conn)

    def get_conn(self):
        """获取数据库连接（为了兼容性保留，但建议使用cursor方法）"""
        return self._pool.get_connection()

    def create_tables(self):
        tables = {
            'players': '''
                CREATE TABLE IF NOT EXISTS players (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL UNIQUE,
                    player_id INT NOT NULL UNIQUE,
                    group_id VARCHAR(64) DEFAULT NULL,
                    name VARCHAR(100) NOT NULL,
                    gold DECIMAL(30,2) DEFAULT 0,
                    diamond INT DEFAULT 0,
                    city_level INT DEFAULT 1,
                    total_income DECIMAL(30,2) DEFAULT 0,
                    tutorial_step INT DEFAULT 1,
                    ticket_normal INT DEFAULT 1,
                    ticket_gold INT DEFAULT 0,
                    ticket_rainbow INT DEFAULT 0,
                    last_checkin_date DATE DEFAULT NULL,
                    consecutive_checkins INT DEFAULT 0,
                    memory_tickets INT DEFAULT 0,
                    current_event JSON DEFAULT NULL,
                    event_expire_time INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_player_id (player_id),
                    INDEX idx_group_id (group_id),
                    INDEX idx_total_income (total_income)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''',
            'player_booths': '''
                CREATE TABLE IF NOT EXISTS player_booths (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    booth_name VARCHAR(50) NOT NULL,
                    unlocked BOOLEAN DEFAULT FALSE,
                    assistant_name VARCHAR(100) DEFAULT NULL,
                    assistant_level INT DEFAULT 1,
                    assistant_star INT DEFAULT 1,
                    last_collect INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_booth (user_id, booth_name),
                    INDEX idx_user_id (user_id),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''',
            'player_assistants': '''
                CREATE TABLE IF NOT EXISTS player_assistants (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    assistant_name VARCHAR(100) NOT NULL,
                    level INT DEFAULT 1,
                    star INT DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_assistant (user_id, assistant_name),
                    INDEX idx_user_id (user_id),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''',
            'player_fragments': '''
                CREATE TABLE IF NOT EXISTS player_fragments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    assistant_name VARCHAR(100) NOT NULL,
                    count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_fragment (user_id, assistant_name),
                    INDEX idx_user_id (user_id),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''',
            'player_memory_parts': '''
                CREATE TABLE IF NOT EXISTS player_memory_parts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    card_part_key VARCHAR(150) NOT NULL,
                    count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_memory_part (user_id, card_part_key),
                    INDEX idx_user_id (user_id),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''',
            'player_memory_cards': '''
                CREATE TABLE IF NOT EXISTS player_memory_cards (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    card_name VARCHAR(100) NOT NULL,
                    count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_memory_card (user_id, card_name),
                    INDEX idx_user_id (user_id),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''',
            'world_ranking': '''
                CREATE TABLE IF NOT EXISTS world_ranking (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL UNIQUE,
                    name VARCHAR(100) NOT NULL,
                    gold DECIMAL(30,2) DEFAULT 0,
                    total_income DECIMAL(30,2) DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_total_income (total_income DESC),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''',
            'player_friends': '''
                CREATE TABLE IF NOT EXISTS player_friends (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    friend_user_id VARCHAR(128) NOT NULL,
                    friend_player_id INT NOT NULL,
                    status ENUM('pending', 'accepted', 'blocked') DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_friendship (user_id, friend_user_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_friend_player_id (friend_player_id),
                    INDEX idx_status (status),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (friend_user_id) REFERENCES players(user_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            '''
        }
        conn = None
        try:
            conn = self._pool.get_connection()
            with conn.cursor() as cur:
                for table, sql in tables.items():
                    try:
                        cur.execute(sql)
                        print(f"表 {table} 创建成功")
                    except Exception as e:
                        print(f"创建表 {table} 失败: {e}")
                        raise
            conn.commit()
        finally:
            if conn:
                self._pool.return_connection(conn)

    @staticmethod
    def get_user_id(e):
        return getattr(e, 'user_id', None)

    @staticmethod
    def parse_user_id(user_id):
        return {'group_id': None, 'user_id': user_id}

    def load_player(self, user_id):
        try:
            with self.cursor() as cur:
                cur.execute("SELECT * FROM players WHERE user_id = %s", (user_id,))
                player = cur.fetchone()
                if not player:
                    return None
                playerData = {
                    'name': player[4],
                    'player_id': int(player[2]),
                    'gold': float(player[5]),
                    'diamond': int(player[6]),
                    'city_level': int(player[7]),
                    'total_income': float(player[8]),
                    'tutorial_step': int(player[9]),
                    'tickets': {
                        '普通': int(player[10]),
                        '黄金': int(player[11]),
                        '炫彩': int(player[12])
                    },
                    'last_checkin_date': player[13],
                    'consecutive_checkins': int(player[14]),
                    'memory_tickets': int(player[15]),
                    'current_event': json.loads(player[16]) if player[16] else None,
                    'event_expire_time': int(player[17])
                }
                playerData['booths'] = self.load_player_booths(user_id)
                playerData['assistants'] = self.load_player_assistants(user_id)
                playerData['fragments'] = self.load_player_fragments(user_id)
                playerData['memory_parts'] = self.load_player_memory_parts(user_id)
                playerData['memory_cards'] = self.load_player_memory_cards(user_id)
                playerData['memory_effects'] = []
                return playerData
        except Exception as e:
            print(f"加载玩家数据失败: {e}")
            return None

    def save_player(self, user_id, player_data):
        """优化的保存玩家数据方法，减少数据库锁定时间"""
        conn = None
        start_time = time.time()
        
        try:
            # 设置连接超时
            conn = self._pool.get_connection()
            
            # 设置事务隔离级别为READ COMMITTED，减少锁等待
            conn.query("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
            
            # 使用较短的锁等待超时（30秒）
            conn.query("SET SESSION innodb_lock_wait_timeout = 30")
            
            # 开始事务
            conn.begin()
            
            user_info = self.parse_user_id(user_id)
            
            # 优化：使用批量操作，减少SQL执行次数
            self._save_player_optimized(conn, user_id, user_info, player_data)
            
            # 提交事务
            conn.commit()
            
            # 记录执行时间
            execution_time = time.time() - start_time
            if execution_time > 2.0:  # 如果执行时间超过2秒，记录警告
                print(f"警告: save_player执行时间较长: {execution_time:.2f}秒")
            
            return True
            
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            
            execution_time = time.time() - start_time
            print(f"保存玩家数据失败 (用时{execution_time:.2f}秒): {e}")
            
            # 如果是锁等待超时，返回特定错误信息
            if "Lock wait timeout" in str(e):
                print(f"数据库锁等待超时，用户{user_id}的数据保存被跳过")
                return False
            
            return False
            
        finally:
            if conn:
                try:
                    # 重置会话设置
                    conn.query("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                    conn.query("SET SESSION innodb_lock_wait_timeout = 50")
                except:
                    pass
                self._pool.return_connection(conn)

    def _save_player_optimized(self, conn, user_id, user_info, player_data):
        """优化的批量保存方法，减少数据库交互次数"""
        with conn.cursor() as cur:
            # 1. 保存基础玩家信息
            player_id = player_data.get('player_id') or self.get_next_player_id()
            tickets = player_data.get('tickets', {'普通': 1, '黄金': 0, '炫彩': 0})
            
            # 使用REPLACE INTO替代INSERT ... ON DUPLICATE KEY UPDATE，性能更好
            cur.execute('''REPLACE INTO players (
                user_id, player_id, group_id, name, gold, diamond, city_level, total_income,
                tutorial_step, ticket_normal, ticket_gold, ticket_rainbow,
                last_checkin_date, consecutive_checkins, memory_tickets,
                current_event, event_expire_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''', [
                user_id, player_id, user_info['group_id'],
                player_data.get('name', '未知玩家'),
                player_data.get('gold', 0), player_data.get('diamond', 0),
                player_data.get('city_level', 1), player_data.get('total_income', 0),
                player_data.get('tutorial_step', 1),
                tickets.get('普通', 1), tickets.get('黄金', 0), tickets.get('炫彩', 0),
                player_data.get('last_checkin_date'),
                player_data.get('consecutive_checkins', 0),
                player_data.get('memory_tickets', 0),
                json.dumps(player_data.get('current_event')) if player_data.get('current_event') else None,
                player_data.get('event_expire_time', 0)
            ])
            
            # 2. 批量删除旧的子表数据
            delete_queries = [
                "DELETE FROM player_booths WHERE user_id = %s",
                "DELETE FROM player_assistants WHERE user_id = %s", 
                "DELETE FROM player_fragments WHERE user_id = %s",
                "DELETE FROM player_memory_parts WHERE user_id = %s",
                "DELETE FROM player_memory_cards WHERE user_id = %s"
            ]
            
            for query in delete_queries:
                cur.execute(query, (user_id,))
            
            # 3. 批量插入摊位数据
            booths = player_data.get('booths', {})
            if booths:
                booth_values = []
                for booth_name, booth_data in booths.items():
                    assistant = booth_data.get('assistant')
                    unlocked_value = booth_data.get('unlocked', False)
                    unlocked = 1 if (unlocked_value and unlocked_value not in ('', None, 'false', '0')) else 0
                    
                    booth_values.append([
                        user_id, booth_name, unlocked,
                        assistant['name'] if assistant else None,
                        assistant.get('level', 1) if assistant else 1,
                        assistant.get('star', 1) if assistant else 1,
                        booth_data.get('last_collect', 0)
                    ])
                
                if booth_values:
                    cur.executemany('''INSERT INTO player_booths (
                        user_id, booth_name, unlocked, assistant_name, assistant_level, assistant_star, last_collect
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)''', booth_values)
            
            # 4. 批量插入助理数据
            assistants = player_data.get('assistants', [])
            if assistants:
                assistant_values = [[user_id, assistant.get('name', '未知助理'), 
                                   assistant.get('level', 1), assistant.get('star', 1)] 
                                  for assistant in assistants]
                cur.executemany('''INSERT INTO player_assistants 
                    (user_id, assistant_name, level, star) VALUES (%s, %s, %s, %s)''', assistant_values)
            
            # 5. 批量插入碎片数据
            fragments = player_data.get('fragments', {})
            if fragments:
                fragment_values = [[user_id, name, count] for name, count in fragments.items() if count > 0]
                if fragment_values:
                    cur.executemany('''INSERT INTO player_fragments 
                        (user_id, assistant_name, count) VALUES (%s, %s, %s)''', fragment_values)
            
            # 6. 批量插入记忆碎片数据
            memory_parts = player_data.get('memory_parts', {})
            if memory_parts:
                memory_part_values = [[user_id, key, count] for key, count in memory_parts.items() if count > 0]
                if memory_part_values:
                    cur.executemany('''INSERT INTO player_memory_parts 
                        (user_id, card_part_key, count) VALUES (%s, %s, %s)''', memory_part_values)
            
            # 7. 批量插入记忆卡片数据  
            memory_cards = player_data.get('memory_cards', {})
            if memory_cards:
                memory_card_values = [[user_id, name, count] for name, count in memory_cards.items() if count > 0]
                if memory_card_values:
                    cur.executemany('''INSERT INTO player_memory_cards 
                        (user_id, card_name, count) VALUES (%s, %s, %s)''', memory_card_values)

    def save_player_with_retry(self, user_id, player_data, max_retries=3):
        """带重试机制的保存方法，处理锁等待问题"""
        for attempt in range(max_retries):
            try:
                result = self.save_player(user_id, player_data)
                if result:
                    return True
                    
                # 如果失败，短暂等待后重试
                if attempt < max_retries - 1:
                    wait_time = 0.1 * (2 ** attempt)  # 指数退避：0.1s, 0.2s, 0.4s
                    print(f"保存失败，{wait_time}秒后重试 (第{attempt + 1}次)")
                    time.sleep(wait_time)
                    
            except Exception as e:
                if "Lock wait timeout" in str(e) and attempt < max_retries - 1:
                    wait_time = 0.5 * (2 ** attempt)  # 锁超时时等待更长时间
                    print(f"锁等待超时，{wait_time}秒后重试 (第{attempt + 1}次)")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"保存失败，不再重试: {e}")
                    break
                    
        print(f"用户 {user_id} 数据保存失败，已尝试 {max_retries} 次")
        return False

    def save_player_async_queue(self, user_id, player_data):
        """将保存任务加入异步队列（可选实现）"""
        # 这里可以实现一个异步保存队列
        # 避免在主线程中等待数据库锁
        # 可以使用线程池或异步任务队列
        pass

    def load_player_booths(self, user_id):
        with self.cursor() as cur:
            cur.execute("SELECT * FROM player_booths WHERE user_id = %s", (user_id,))
            booths = {}
            for row in cur.fetchall():
                assistant = None
                if row[4]:
                    assistant = {
                        'name': row[4],
                        'level': int(row[5]),
                        'star': int(row[6])
                    }
                booths[row[2]] = {
                    'unlocked': bool(row[3]),
                    'assistant': assistant,
                    'last_collect': int(row[7])
                }
            return booths

    def load_player_assistants(self, user_id):
        with self.cursor() as cur:
            cur.execute("SELECT * FROM player_assistants WHERE user_id = %s", (user_id,))
            assistants = []
            for row in cur.fetchall():
                assistants.append({
                    'name': row[2],
                    'level': int(row[3]),
                    'star': int(row[4])
                })
            return assistants

    def load_player_fragments(self, user_id):
        with self.cursor() as cur:
            cur.execute("SELECT * FROM player_fragments WHERE user_id = %s AND count > 0", (user_id,))
            fragments = {}
            for row in cur.fetchall():
                fragments[row[2]] = int(row[3])
            return fragments

    def load_player_memory_parts(self, user_id):
        with self.cursor() as cur:
            cur.execute("SELECT * FROM player_memory_parts WHERE user_id = %s AND count > 0", (user_id,))
            memory_parts = {}
            for row in cur.fetchall():
                memory_parts[row[2]] = int(row[3])
            return memory_parts

    def load_player_memory_cards(self, user_id):
        with self.cursor() as cur:
            cur.execute("SELECT * FROM player_memory_cards WHERE user_id = %s AND count > 0", (user_id,))
            memory_cards = {}
            for row in cur.fetchall():
                memory_cards[row[2]] = int(row[3])
            return memory_cards

    def save_player_basic(self, user_id, user_info, player_data, conn=None):
        player_id = player_data.get('player_id') or self.get_next_player_id()
        tickets = player_data.get('tickets', {'普通': 1, '黄金': 0, '炫彩': 0})
        sql = '''INSERT INTO players (
            user_id, player_id, group_id, name, gold, diamond, city_level, total_income,
            tutorial_step, ticket_normal, ticket_gold, ticket_rainbow,
            last_checkin_date, consecutive_checkins, memory_tickets,
            current_event, event_expire_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), gold=VALUES(gold), diamond=VALUES(diamond), city_level=VALUES(city_level),
            total_income=VALUES(total_income), tutorial_step=VALUES(tutorial_step), ticket_normal=VALUES(ticket_normal),
            ticket_gold=VALUES(ticket_gold), ticket_rainbow=VALUES(ticket_rainbow), last_checkin_date=VALUES(last_checkin_date),
            consecutive_checkins=VALUES(consecutive_checkins), memory_tickets=VALUES(memory_tickets),
            current_event=VALUES(current_event), event_expire_time=VALUES(event_expire_time)'''
        
        if conn:
            with conn.cursor() as cur:
                cur.execute(sql, [
                    user_id,
                    player_id,
                    user_info['group_id'],
                    player_data.get('name', '未知玩家'),
                    player_data.get('gold', 0),
                    player_data.get('diamond', 0),
                    player_data.get('city_level', 1),
                    player_data.get('total_income', 0),
                    player_data.get('tutorial_step', 1),
                    tickets.get('普通', 1),
                    tickets.get('黄金', 0),
                    tickets.get('炫彩', 0),
                    player_data.get('last_checkin_date'),
                    player_data.get('consecutive_checkins', 0),
                    player_data.get('memory_tickets', 0),
                    json.dumps(player_data.get('current_event')) if player_data.get('current_event') else None,
                    player_data.get('event_expire_time', 0)
                ])
        else:
            with self.cursor() as cur:
                cur.execute(sql, [
                    user_id,
                    player_id,
                    user_info['group_id'],
                    player_data.get('name', '未知玩家'),
                    player_data.get('gold', 0),
                    player_data.get('diamond', 0),
                    player_data.get('city_level', 1),
                    player_data.get('total_income', 0),
                    player_data.get('tutorial_step', 1),
                    tickets.get('普通', 1),
                    tickets.get('黄金', 0),
                    tickets.get('炫彩', 0),
                    player_data.get('last_checkin_date'),
                    player_data.get('consecutive_checkins', 0),
                    player_data.get('memory_tickets', 0),
                    json.dumps(player_data.get('current_event')) if player_data.get('current_event') else None,
                    player_data.get('event_expire_time', 0)
                ])

    def save_player_booths(self, user_id, booths, conn=None):
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM player_booths WHERE user_id = %s", (user_id,))
                if not booths:
                    return
                sql = '''INSERT INTO player_booths (
                    user_id, booth_name, unlocked, assistant_name, assistant_level, assistant_star, last_collect
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)'''
                for booth_name, booth_data in booths.items():
                    assistant = booth_data.get('assistant')
                    unlocked_value = booth_data.get('unlocked', False)
                    if unlocked_value in ('', None):
                        unlocked = False
                    elif isinstance(unlocked_value, str):
                        unlocked = unlocked_value in ('true', '1')
                    else:
                        unlocked = bool(unlocked_value)
                    cur.execute(sql, [
                        user_id,
                        booth_name,
                        1 if unlocked else 0,
                        assistant['name'] if assistant else None,
                        assistant.get('level', 1) if assistant else 1,
                        assistant.get('star', 1) if assistant else 1,
                        booth_data.get('last_collect', 0)
                    ])
        else:
            with self.cursor() as cur:
                cur.execute("DELETE FROM player_booths WHERE user_id = %s", (user_id,))
                if not booths:
                    return
                sql = '''INSERT INTO player_booths (
                    user_id, booth_name, unlocked, assistant_name, assistant_level, assistant_star, last_collect
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)'''
                for booth_name, booth_data in booths.items():
                    assistant = booth_data.get('assistant')
                    unlocked_value = booth_data.get('unlocked', False)
                    if unlocked_value in ('', None):
                        unlocked = False
                    elif isinstance(unlocked_value, str):
                        unlocked = unlocked_value in ('true', '1')
                    else:
                        unlocked = bool(unlocked_value)
                    cur.execute(sql, [
                        user_id,
                        booth_name,
                        1 if unlocked else 0,
                        assistant['name'] if assistant else None,
                        assistant.get('level', 1) if assistant else 1,
                        assistant.get('star', 1) if assistant else 1,
                        booth_data.get('last_collect', 0)
                    ])

    def save_player_assistants(self, user_id, assistants, conn=None):
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM player_assistants WHERE user_id = %s", (user_id,))
                if not assistants:
                    return
                sql = "INSERT INTO player_assistants (user_id, assistant_name, level, star) VALUES (%s, %s, %s, %s)"
                for assistant in assistants:
                    cur.execute(sql, [
                        user_id,
                        assistant.get('name', '未知助理'),
                        assistant.get('level', 1),
                        assistant.get('star', 1)
                    ])
        else:
            with self.cursor() as cur:
                cur.execute("DELETE FROM player_assistants WHERE user_id = %s", (user_id,))
                if not assistants:
                    return
                sql = "INSERT INTO player_assistants (user_id, assistant_name, level, star) VALUES (%s, %s, %s, %s)"
                for assistant in assistants:
                    cur.execute(sql, [
                        user_id,
                        assistant.get('name', '未知助理'),
                        assistant.get('level', 1),
                        assistant.get('star', 1)
                    ])

    def save_player_fragments(self, user_id, fragments, conn=None):
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM player_fragments WHERE user_id = %s", (user_id,))
                if not fragments:
                    return
                sql = "INSERT INTO player_fragments (user_id, assistant_name, count) VALUES (%s, %s, %s)"
                for assistant_name, count in fragments.items():
                    if count > 0:
                        cur.execute(sql, [user_id, assistant_name, count])
        else:
            with self.cursor() as cur:
                cur.execute("DELETE FROM player_fragments WHERE user_id = %s", (user_id,))
                if not fragments:
                    return
                sql = "INSERT INTO player_fragments (user_id, assistant_name, count) VALUES (%s, %s, %s)"
                for assistant_name, count in fragments.items():
                    if count > 0:
                        cur.execute(sql, [user_id, assistant_name, count])

    def save_player_memory_parts(self, user_id, memory_parts, conn=None):
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM player_memory_parts WHERE user_id = %s", (user_id,))
                if not memory_parts:
                    return
                sql = "INSERT INTO player_memory_parts (user_id, card_part_key, count) VALUES (%s, %s, %s)"
                for part_key, count in memory_parts.items():
                    if count > 0:
                        cur.execute(sql, [user_id, part_key, count])
        else:
            with self.cursor() as cur:
                cur.execute("DELETE FROM player_memory_parts WHERE user_id = %s", (user_id,))
                if not memory_parts:
                    return
                sql = "INSERT INTO player_memory_parts (user_id, card_part_key, count) VALUES (%s, %s, %s)"
                for part_key, count in memory_parts.items():
                    if count > 0:
                        cur.execute(sql, [user_id, part_key, count])

    def save_player_memory_cards(self, user_id, memory_cards, conn=None):
        if conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM player_memory_cards WHERE user_id = %s", (user_id,))
                if not memory_cards:
                    return
                sql = "INSERT INTO player_memory_cards (user_id, card_name, count) VALUES (%s, %s, %s)"
                for card_name, count in memory_cards.items():
                    if count > 0:
                        cur.execute(sql, [user_id, card_name, count])
        else:
            with self.cursor() as cur:
                cur.execute("DELETE FROM player_memory_cards WHERE user_id = %s", (user_id,))
                if not memory_cards:
                    return
                sql = "INSERT INTO player_memory_cards (user_id, card_name, count) VALUES (%s, %s, %s)"
                for card_name, count in memory_cards.items():
                    if count > 0:
                        cur.execute(sql, [user_id, card_name, count])

    def load_world_ranking(self):
        with self.cursor() as cur:
            cur.execute("SELECT name, gold, total_income FROM world_ranking ORDER BY total_income DESC LIMIT 50")
            return [
                {'name': row[0], 'gold': float(row[1]), 'total_income': float(row[2])}
                for row in cur.fetchall()
            ]

    def update_world_ranking(self, user_id, name, gold, total_income):
        """更新世界排行榜数据"""
        conn = None
        try:
            conn = self._pool.get_connection()
            sql = '''INSERT INTO world_ranking (user_id, name, gold, total_income)
                     VALUES (%s, %s, %s, %s)
                     ON DUPLICATE KEY UPDATE
                        name=VALUES(name), gold=VALUES(gold), total_income=VALUES(total_income)'''
            with conn.cursor() as cur:
                cur.execute(sql, [user_id, name, gold, total_income])
            conn.commit()  # 重要：提交事务
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"更新世界排行榜失败: {e}")
            return False
        finally:
            if conn:
                self._pool.return_connection(conn)

    def get_next_player_id(self):
        with self.cursor() as cur:
            cur.execute('SELECT MAX(player_id) FROM players')
            max_id = cur.fetchone()[0]
            return (max_id or 0) + 1

    def get_user_by_player_id(self, player_id):
        with self.cursor() as cur:
            cur.execute('SELECT * FROM players WHERE player_id = %s', (player_id,))
            return cur.fetchone()

    def get_player_id_by_user_id(self, user_id):
        with self.cursor() as cur:
            cur.execute('SELECT player_id FROM players WHERE user_id = %s', (user_id,))
            result = cur.fetchone()
            return int(result[0]) if result and result[0] else None

    def add_friend(self, user_id, friend_player_id):
        conn = None
        try:
            friend_user = self.get_user_by_player_id(friend_player_id)
            if not friend_user:
                return {'success': False, 'message': '玩家ID不存在'}
            friend_user_id = friend_user[1]
            
            conn = self._pool.get_connection()
            with conn.cursor() as cur:
                cur.execute('SELECT status FROM player_friends WHERE user_id = %s AND friend_user_id = %s', (user_id, friend_user_id))
                existing = cur.fetchone()
                if existing:
                    if existing[0] == 'accepted':
                        return {'success': False, 'message': '已经是好友了'}
                    elif existing[0] == 'pending':
                        return {'success': False, 'message': '好友请求已发送，等待对方同意'}
                    elif existing[0] == 'blocked':
                        return {'success': False, 'message': '无法添加此玩家为好友'}
                cur.execute('INSERT INTO player_friends (user_id, friend_user_id, friend_player_id, status) VALUES (%s, %s, %s, %s)', (user_id, friend_user_id, friend_player_id, 'pending'))
            conn.commit()
            return {'success': True, 'message': '好友请求已发送'}
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"添加好友失败: {e}")
            return {'success': False, 'message': '添加好友失败'}
        finally:
            if conn:
                self._pool.return_connection(conn)

    def get_friends(self, user_id):
        try:
            with self.cursor() as cur:
                cur.execute('''SELECT p.player_id, p.name, p.city_level, p.total_income, pf.created_at as friend_since
                               FROM player_friends pf
                               JOIN players p ON pf.friend_user_id = p.user_id
                               WHERE pf.user_id = %s AND pf.status = 'accepted'
                               ORDER BY pf.created_at DESC''', (user_id,))
                return cur.fetchall()
        except Exception as e:
            print(f"获取好友列表失败: {e}")
            return []

    def get_friend_requests(self, user_id):
        try:
            with self.cursor() as cur:
                cur.execute('''SELECT p.player_id, p.name, p.city_level, p.total_income, pf.created_at as request_time
                               FROM player_friends pf
                               JOIN players p ON pf.user_id = p.user_id
                               WHERE pf.friend_user_id = %s AND pf.status = 'pending'
                               ORDER BY pf.created_at DESC''', (user_id,))
                return cur.fetchall()
        except Exception as e:
            print(f"获取好友请求失败: {e}")
            return []

    def get_pool_status(self):
        """获取连接池状态信息"""
        if self._pool:
            with self._pool._lock:
                return {
                    'pool_size': self._pool.pool_size,
                    'max_overflow': self._pool.max_overflow,
                    'created_connections': self._pool._created_connections,
                    'available_connections': self._pool._pool.qsize()
                }
        return None

    def close_pool(self):
        """关闭连接池"""
        if self._pool:
            self._pool.close_all()
            IdleTycoonDatabase._pool = None

    @classmethod
    def recreate_pool(cls):
        """重新创建连接池"""
        if cls._pool:
            cls._pool.close_all()
        cls._pool = None
        if cls._instance:
            cls._instance.__init__()
