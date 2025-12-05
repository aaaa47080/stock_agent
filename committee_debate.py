"""
委員會辯論模組
實現多模型委員會式辯論：多個模型給出同一方觀點後綜合
"""

import json
from typing import List, Dict
from models import AnalystReport, ResearcherDebate
from llm_client import create_llm_client_from_config, supports_json_mode
from agents import BullResearcher, BearResearcher


class CommitteeDebate:
    """委員會辯論系統"""

    def __init__(self, synthesis_model_config: Dict):
        """
        初始化委員會辯論

        Args:
            synthesis_model_config: 綜合模型配置
        """
        self.synthesis_client, self.synthesis_model = create_llm_client_from_config(
            synthesis_model_config
        )

    def bull_committee_debate(
        self,
        analyst_reports: List[AnalystReport],
        committee_configs: List[Dict]
    ) -> ResearcherDebate:
        """
        多頭委員會辯論

        Args:
            analyst_reports: 分析師報告
            committee_configs: 委員會成員配置列表

        Returns:
            綜合後的多頭論證
        """
        print(f"\n  🏛️ 多頭委員會開始辯論 ({len(committee_configs)} 位專家)...")

        # 收集所有委員會成員的觀點
        bull_opinions = []

        for i, config in enumerate(committee_configs, 1):
            model_name = config.get("name", config.get("model"))
            print(f"    {i}. {model_name} 正在分析...")

            try:
                # 創建該模型的客戶端
                client, model = create_llm_client_from_config(config)

                # 該模型作為多頭研究員
                researcher = BullResearcher(client, model)
                opinion = researcher.debate(analyst_reports)

                bull_opinions.append({
                    "expert": model_name,
                    "argument": opinion.argument,
                    "key_points": opinion.key_points,
                    "counter_arguments": opinion.counter_arguments,
                    "confidence": opinion.confidence
                })

                print(f"       ✅ 完成 (信心度: {opinion.confidence}%)")

            except Exception as e:
                print(f"       ❌ 失敗: {e}")
                continue

        # 綜合所有觀點
        print(f"    🔄 正在綜合 {len(bull_opinions)} 位專家的觀點...")
        synthesized = self._synthesize_bull_opinions(bull_opinions)

        print(f"    ✅ 多頭委員會論證完成 (綜合信心度: {synthesized.confidence}%)")
        return synthesized

    def bear_committee_debate(
        self,
        analyst_reports: List[AnalystReport],
        committee_configs: List[Dict]
    ) -> ResearcherDebate:
        """
        空頭委員會辯論

        Args:
            analyst_reports: 分析師報告
            committee_configs: 委員會成員配置列表

        Returns:
            綜合後的空頭論證
        """
        print(f"\n  🏛️ 空頭委員會開始辯論 ({len(committee_configs)} 位專家)...")

        # 收集所有委員會成員的觀點
        bear_opinions = []

        for i, config in enumerate(committee_configs, 1):
            model_name = config.get("name", config.get("model"))
            print(f"    {i}. {model_name} 正在分析...")

            try:
                # 創建該模型的客戶端
                client, model = create_llm_client_from_config(config)

                # 該模型作為空頭研究員
                researcher = BearResearcher(client, model)
                opinion = researcher.debate(analyst_reports)

                bear_opinions.append({
                    "expert": model_name,
                    "argument": opinion.argument,
                    "key_points": opinion.key_points,
                    "counter_arguments": opinion.counter_arguments,
                    "confidence": opinion.confidence
                })

                print(f"       ✅ 完成 (信心度: {opinion.confidence}%)")

            except Exception as e:
                print(f"       ❌ 失敗: {e}")
                continue

        # 綜合所有觀點
        print(f"    🔄 正在綜合 {len(bear_opinions)} 位專家的觀點...")
        synthesized = self._synthesize_bear_opinions(bear_opinions)

        print(f"    ✅ 空頭委員會論證完成 (綜合信心度: {synthesized.confidence}%)")
        return synthesized

    def _synthesize_bull_opinions(self, opinions: List[Dict]) -> ResearcherDebate:
        """
        綜合多個多頭觀點

        Args:
            opinions: 多個專家的多頭觀點

        Returns:
            綜合後的多頭論證
        """
        prompt = f"""
你是一位資深的投資委員會主席，負責綜合多位多頭專家的觀點。

以下是 {len(opinions)} 位多頭專家的分析：

{json.dumps(opinions, indent=2, ensure_ascii=False)}

你的任務：
1. 綜合所有專家的看漲論點，提煉出最有說服力的觀點
2. 整合關鍵看漲點，去除重複，保留最重要的
3. 綜合對空頭論點的反駁
4. 計算綜合信心度（考慮所有專家的信心度和觀點一致性）

綜合原則：
- 如果多位專家都提到同一觀點，說明該觀點重要性高
- 如果專家意見分歧大，降低綜合信心度
- 如果專家意見高度一致，提高綜合信心度
- 保留最獨特且有價值的觀點

請以 JSON 格式回覆，嚴格遵守數據類型：
- researcher_stance: "Bull"
- argument: 綜合後的多頭論點 (繁體中文，至少150字，整合所有專家觀點)
- key_points: 綜合後的關鍵看漲點列表 (必須是字串 List，去重後最重要的5-8點)
- counter_arguments: 綜合後的反駁列表 (必須是字串 List)
- confidence: 綜合信心度 (0-100，考慮專家信心度的加權平均和一致性)
"""

        # 根據模型是否支持 JSON 模式來決定是否使用 response_format
        if supports_json_mode(self.synthesis_model):
            response = self.synthesis_client.chat.completions.create(
                model=self.synthesis_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
        else:
            response = self.synthesis_client.chat.completions.create(
                model=self.synthesis_model,
                messages=[{"role": "user", "content": prompt}]
            )

        return ResearcherDebate.model_validate(
            json.loads(response.choices[0].message.content)
        )

    def _synthesize_bear_opinions(self, opinions: List[Dict]) -> ResearcherDebate:
        """
        綜合多個空頭觀點

        Args:
            opinions: 多個專家的空頭觀點

        Returns:
            綜合後的空頭論證
        """
        prompt = f"""
你是一位資深的投資委員會主席，負責綜合多位空頭專家的觀點。

以下是 {len(opinions)} 位空頭專家的分析：

{json.dumps(opinions, indent=2, ensure_ascii=False)}

你的任務：
1. 綜合所有專家的看跌論點和風險警告，提煉出最有說服力的觀點
2. 整合關鍵看跌點，去除重複，保留最重要的風險因素
3. 綜合對多頭論點的反駁
4. 計算綜合信心度（考慮所有專家的信心度和觀點一致性）

綜合原則：
- 如果多位專家都警告同一風險，說明該風險非常重要
- 如果專家意見分歧大，降低綜合信心度
- 如果專家意見高度一致，提高綜合信心度
- 保留最獨特且關鍵的風險點

請以 JSON 格式回覆，嚴格遵守數據類型：
- researcher_stance: "Bear"
- argument: 綜合後的空頭論點 (繁體中文，至少150字，整合所有專家觀點)
- key_points: 綜合後的關鍵看跌點列表 (必須是字串 List，去重後最重要的5-8點)
- counter_arguments: 綜合後的反駁列表 (必須是字串 List)
- confidence: 綜合信心度 (0-100，考慮專家信心度的加權平均和一致性)
"""

        # 根據模型是否支持 JSON 模式來決定是否使用 response_format
        if supports_json_mode(self.synthesis_model):
            response = self.synthesis_client.chat.completions.create(
                model=self.synthesis_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
        else:
            response = self.synthesis_client.chat.completions.create(
                model=self.synthesis_model,
                messages=[{"role": "user", "content": prompt}]
            )

        return ResearcherDebate.model_validate(
            json.loads(response.choices[0].message.content)
        )


# 便捷函數
def run_committee_debate(
    analyst_reports: List[AnalystReport],
    bull_committee_configs: List[Dict],
    bear_committee_configs: List[Dict],
    synthesis_model_config: Dict
) -> tuple:
    """
    運行完整的委員會辯論

    Args:
        analyst_reports: 分析師報告
        bull_committee_configs: 多頭委員會配置
        bear_committee_configs: 空頭委員會配置
        synthesis_model_config: 綜合模型配置

    Returns:
        (bull_argument, bear_argument) 元組
    """
    committee = CommitteeDebate(synthesis_model_config)

    # 多頭委員會辯論
    bull_argument = committee.bull_committee_debate(
        analyst_reports,
        bull_committee_configs
    )

    # 空頭委員會辯論
    bear_argument = committee.bear_committee_debate(
        analyst_reports,
        bear_committee_configs
    )

    return bull_argument, bear_argument
