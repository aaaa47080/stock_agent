"""
資料源配置模組
支持動態註冊和管理多個資料源
"""
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass, field
from core.config import RETRIEVAL_CONFIG, IMAGE_RETRIEVAL_CONFIG

@dataclass
class DataSource:
    """資料源定義"""
    # 基本資訊
    id: str                          # 唯一識別碼，如 "medical_kb", "public_health"
    name: str                        # 顯示名稱，如 "醫療知識庫"
    collection_name: str             # 向量資料庫 collection 名稱
    source_type: Literal["jsonl", "pdf", "web", "api"]  # 資料源類型

    # 檢索配置
    enabled: bool = True             # 是否啟用
    priority: int = 1                # ⚠️ 保留欄位（目前未使用，所有啟用資料源平等檢索）
    default_k: int = 3               # 預設檢索數量

    # 支持的場景
    support_medical: bool = True     # 是否支持醫療問題
    support_procedure: bool = True   # 是否支持醫療程序
    support_general: bool = False    # 是否支持一般問題

    # 額外配置
    metadata: Dict = field(default_factory=dict)  # 額外元數據

    def __post_init__(self):
        """驗證配置"""
        if not self.id or not self.collection_name:
            raise ValueError("id 和 collection_name 不能為空")


# ==================== 預定義資料源 ====================

# 醫療知識庫 (JSONL)
MEDICAL_KB_JSONL = DataSource(
    id="medical_kb_jsonl",
    name="醫療知識庫(JSONL)",
    collection_name="medical_knowledge_base",
    source_type="jsonl",
    priority=10,
    default_k=RETRIEVAL_CONFIG.get("jsonl_k", 3),  # 🔧 增加 k 值以匹配 rag_system_core.py 的檢索數量（原本預設3）
    support_medical=True,
    support_procedure=True,
    metadata={"has_reference": True}  # 包含 reference 欄位，用於動態檢索 PDF
)

# 衛教園地
PUBLIC_HEALTH_EDUCATION = DataSource(
    id="public_health",
    name="衛教園地",
    collection_name="public_health_information_of_education_sites",
    source_type="pdf",
    priority=8,
    default_k=RETRIEVAL_CONFIG.get("public_rag_k", 3),
    support_medical=True,
    support_procedure=True,
    support_general=True
)


# 洗腎衛教 (OCR 資料)
DIALYSIS_EDUCATION = DataSource(
    id="dialysis_education",
    name="洗腎衛教專區",
    collection_name="dialysis_education_materials",
    source_type="pdf",
    priority=9,
    default_k=RETRIEVAL_CONFIG.get("dialysis_rag_k", 3),  # 🔧 使用獨立的洗腎衛教配置
    enabled=True,  # 已啟用
    support_medical=True,
    support_procedure=True,
    metadata={"disease_category": "kidney", "data_source": "ocr"}
)


# 網路醫療資源 (範例 - 假設未來新增)
WEB_MEDICAL_RESOURCES = DataSource(
    id="web_medical",
    name="網路醫療資源",
    collection_name="web_medical_resources",
    source_type="web",
    priority=5,
    enabled=False,  # 預設停用
    support_medical=True,
    support_general=True
)


# 衛教圖片檢索
EDUCATIONAL_IMAGES = DataSource(
    id="educational_images",
    name="衛教圖片檢索",
    collection_name="educational_images",
    source_type="api",
    priority=7,
    default_k=IMAGE_RETRIEVAL_CONFIG.get('educational_images_k', 3),
    enabled=True,
    support_medical=True,
    support_procedure=False,
    support_general=True,
    metadata={"description": "根據問題檢索相關的醫療衛教圖片"}
)


# ==================== 資料源註冊表 ====================

class DataSourceRegistry:
    """資料源註冊表管理器"""

    def __init__(self):
        self._sources: Dict[str, DataSource] = {}
        self._register_defaults()

    def _register_defaults(self):
        """註冊預設資料源"""
        self.register(MEDICAL_KB_JSONL)
        self.register(PUBLIC_HEALTH_EDUCATION)
        self.register(DIALYSIS_EDUCATION)  # 洗腎衛教專區
        self.register(EDUCATIONAL_IMAGES)  # 衛教圖片檢索
        # self.register(WEB_MEDICAL_RESOURCES)

    def register(self, source: DataSource):
        """註冊新資料源"""
        # if source.id in self._sources:
        #     print(f"⚠️ 資料源 '{source.id}' 已存在，將被覆蓋")
        self._sources[source.id] = source
        # print(f"✅ 註冊資料源: {source.name} (id={source.id})")

    def unregister(self, source_id: str):
        """移除資料源"""
        if source_id in self._sources:
            del self._sources[source_id]
            print(f"🗑️ 移除資料源: {source_id}")

    def get(self, source_id: str) -> Optional[DataSource]:
        """獲取資料源"""
        return self._sources.get(source_id)

    def get_all(self) -> List[DataSource]:
        """獲取所有資料源"""
        return list(self._sources.values())

    def get_enabled(self) -> List[DataSource]:
        """獲取已啟用的資料源"""
        return [s for s in self._sources.values() if s.enabled]

    def get_by_scenario(
        self,
        is_medical: bool = False,
        is_procedure: bool = False,
        is_general: bool = False
    ) -> List[DataSource]:
        """根據場景獲取適用的資料源（按註冊順序返回，不排序）

        注意：目前設計為平等檢索所有符合條件的啟用資料源，
        不使用 priority 欄位進行排序或優先選擇。
        """
        sources = []
        for source in self.get_enabled():
            if is_medical and source.support_medical:
                sources.append(source)
            elif is_procedure and source.support_procedure:
                sources.append(source)
            elif is_general and source.support_general:
                sources.append(source)

        # ⚠️ 不使用 priority 排序，保持註冊順序（平等檢索所有資料源）
        return sources

    def enable(self, source_id: str):
        """啟用資料源"""
        if source_id in self._sources:
            self._sources[source_id].enabled = True
            # print(f"✅ 啟用資料源: {source_id}")

    def disable(self, source_id: str):
        """停用資料源"""
        if source_id in self._sources:
            self._sources[source_id].enabled = False
            print(f"🔒 停用資料源: {source_id}")

    def list_sources(self, enabled_only: bool = False):
        """列出所有資料源"""
        sources = self.get_enabled() if enabled_only else self.get_all()
        # print("\n" + "="*60)
        # print(f"📚 資料源列表 {'(僅顯示已啟用)' if enabled_only else ''}")
        # print("="*60)
        for source in sources:
            status = "✅ 啟用" if source.enabled else "🔒 停用"
            # print(f"{status} {source.name}")
            # print(f"     ID: {source.id}")
            # print(f"     Collection: {source.collection_name}")
            # print(f"     類型: {source.source_type}")
            scenarios = []
            if source.support_medical:
                scenarios.append("醫療")
            if source.support_procedure:
                scenarios.append("程序")
            if source.support_general:
                scenarios.append("一般")
            print(f"     支持場景: {', '.join(scenarios)}")
            print()


# ==================== 全局註冊表實例 ====================

_global_registry = DataSourceRegistry()


def get_registry() -> DataSourceRegistry:
    """獲取全局資料源註冊表"""
    return _global_registry


# ==================== 便捷函數 ====================

def register_datasource(source: DataSource):
    """註冊新資料源（便捷函數）"""
    _global_registry.register(source)


def get_datasource(source_id: str) -> Optional[DataSource]:
    """獲取資料源（便捷函數）"""
    return _global_registry.get(source_id)


def list_datasources(enabled_only: bool = False):
    """列出所有資料源（便捷函數）"""
    _global_registry.list_sources(enabled_only)


def enable_datasource(source_id: str):
    """啟用資料源（便捷函數）"""
    _global_registry.enable(source_id)


def disable_datasource(source_id: str):
    """停用資料源（便捷函數）"""
    _global_registry.disable(source_id)


# ==================== 使用範例 ====================

if __name__ == "__main__":
    print("🚀 資料源配置系統演示\n")

    # 列出所有資料源
    list_datasources(enabled_only=False)

    # 啟用特定資料源
    print("📌 啟用糖尿病衛教專區...")
    enable_datasource("diabetes_education")

    print("\n📌 啟用洗腎衛教專區...")
    enable_datasource("dialysis_education")

    # 列出已啟用的資料源
    list_datasources(enabled_only=True)

    # 根據場景獲取資料源
    print("\n" + "="*60)
    print("🔍 根據場景查詢資料源")
    print("="*60)

    medical_sources = get_registry().get_by_scenario(is_medical=True)
    print(f"\n醫療場景適用資料源 ({len(medical_sources)} 個):")
    for s in medical_sources:
        print(f"  [{s.priority}] {s.name} ({s.id})")

    procedure_sources = get_registry().get_by_scenario(is_procedure=True)
    print(f"\n程序場景適用資料源 ({len(procedure_sources)} 個):")
    for s in procedure_sources:
        print(f"  [{s.priority}] {s.name} ({s.id})")

    # 動態註冊新資料源
    print("\n" + "="*60)
    print("🆕 動態註冊新資料源")
    print("="*60)

    custom_source = DataSource(
        id="custom_health_tips",
        name="健康小知識",
        collection_name="health_tips_collection",
        source_type="web",
        priority=6,
        support_general=True,
        metadata={"language": "zh-TW"}
    )
    register_datasource(custom_source)

    print("\n✅ 演示完成！")
