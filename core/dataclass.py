from pydantic import BaseModel, Field
from typing import Optional, List
import re


class ValidationResult(BaseModel):
    validation_type: str = Field(
        description="One of: 'pass', 'regenerate', 'need_more_knowledge'"
    )
    is_valid: bool = Field(description="True if answer is acceptable, False otherwise")
    feedback: Optional[str] = Field(
        default=None,
        description="Explanation of the validation decision"
    )
    missing_info: Optional[str] = Field(
        default=None,
        description="Specific missing information needed if validation_type is 'need_more_knowledge'"
    )
    suggested_sub_questions: Optional[List[str]] = Field(
        default=None,
        description="Suggested sub-questions for retrieving missing information (when validation_type is 'need_more_knowledge')"
    )


class QueryComplexityResult(BaseModel):
    is_complex: bool = Field(description="True if query has ≥2 medical entities")
    search_strategy: str = Field(description="Either 'simple' or 'entity_based'")
    extracted_entities: List[str] = Field(default_factory=list)
    reasoning: str = Field(description="Explanation for the decision")


class RetrievalStep(BaseModel):
    """單個檢索步驟"""
    step: int = Field(description="步驟編號 (從1開始)")
    query: str = Field(description="這一步要檢索的問題")
    purpose: str = Field(description="這一步的目的和預期獲得的資訊")


class QueryPlanningResult(BaseModel):
    """查詢規劃結果"""
    needs_planning: bool = Field(description="是否需要分步檢索")
    reasoning: str = Field(description="判斷理由：為什麼需要/不需要分步")
    retrieval_steps: List[RetrievalStep] = Field(
        default_factory=list,
        description="檢索步驟列表（如果 needs_planning=False 則為空）"
    )


class ReferenceSource(BaseModel):
    """參考文獻來源"""
    filename: str = Field(description="文件檔名（如：發燒、咳嗽及腹瀉監測與自主健康管理作業準則.pdf）")
    content: str = Field(description="從該文件中提取的相關內容")
    page: Optional[str] = Field(default=None, description="頁碼（如果有的話）")


class MedicalResponse(BaseModel):


    """結構化醫療回應"""


    summary: str = Field(


        description="綜合建議：對問題的完整回答和建議"


    )


    references: List[ReferenceSource] = Field(


        default_factory=list,


        description="參考依據：支持回答的參考文獻列表"


    )


    matched_table_images: List[dict] = Field(


        default_factory=list,


        description="匹配到的表格圖片列表"


    )


    matched_educational_images: List[dict] = Field(


        default_factory=list,


        description="匹配到的衛教圖片列表"


    )


    query_type: Optional[str] = Field(


        default=None,


        description="問題類型：rag_needed, greet, out_of_scope 等"


    )





    def to_formatted_text(self) -> str:


        """


        將結構化回應轉換為格式化文本





        Returns:


            格式化後的文本


            - 有參考文獻：顯示「綜合建議」標題 + 內容 + 「參考依據」


            - 無參考文獻：直接顯示內容，不加「綜合建議」標題


        """


        parts = []





        # 判斷是否有參考文獻


        has_references = self.references and len(self.references) > 0





        if has_references:


            # 有參考文獻：顯示「綜合建議」標題


            if self.summary:


                parts.append("**綜合建議**")


                parts.append(self.summary)





            # 顯示參考依據


            parts.append("\n**參考依據**\n")


            for ref in self.references:


                parts.append(f"《{ref.filename}》")


                parts.append(ref.content)


                if ref.page:


                    parts.append(f"（頁碼：{ref.page}）")


                parts.append("")  # 空行分隔


        else:


            # 無參考文獻：直接顯示內容，不加標題


            if self.summary:


                parts.append(self.summary)





        # 🆕 加入圖片區塊（純文本預覽）


        if self.matched_educational_images:


            parts.append("\n**🖼️ 相關衛教圖片**")


            for idx, img in enumerate(self.matched_educational_images, 1):


                parts.append(f"{idx}. {img.get('health_topic', '衛教圖片')}")





        if self.matched_table_images:


            parts.append("\n**📊 相關表格圖片**")


            for idx, img in enumerate(self.matched_table_images, 1):


                parts.append(f"{idx}. 表格圖片")





        return "\n".join(parts)





    def to_dict(self) -> dict:


        """


        轉換為字典格式，方便 JSON 序列化


        """


        return {


            "summary": self.summary,


            "references": [


                {


                    "filename": ref.filename,


                    "content": ref.content,


                    "page": ref.page


                }


                for ref in self.references


            ],


            "matched_table_images": self.matched_table_images,


            "matched_educational_images": self.matched_educational_images,


            "query_type": self.query_type


        }





    @classmethod


    def parse_from_text(cls, text: str, query_type: Optional[str] = None) -> "MedicalResponse":


        """


        從現有的文本格式解析出結構化的 MedicalResponse


        （注意：此方法無法還原圖片對象，僅用於文本解析）


        """


        summary = ""


        references = []





        # 檢查是否包含 **參考依據** 標籤


        has_ref_section = '**參考依據**' in text





        # 分割綜合建議和參考依據 (也移除圖片區塊)


        clean_text = text


        for section_marker in ['**相關衛教圖片**', '**相關表格圖片**', '**🖼️ 相關衛教圖片**', '**📊 相關表格圖片**']:


            if section_marker in clean_text:


                clean_text = clean_text.split(section_marker)[0]





        if has_ref_section:


            parts = re.split(r'\*\*參考依據\*\*', clean_text, maxsplit=1)


        else:


            parts = [clean_text]





        # 提取綜合建議


        summary_part = parts[0]





        # 檢查是否有 **綜合建議** 標籤


        if '**綜合建議**' in summary_part:


            summary_match = re.search(r'\*\*綜合建議\*\*\s*(.*)', summary_part, re.DOTALL)


            if summary_match:


                summary = summary_match.group(1).strip()


            else:


                summary = summary_part.replace('**綜合建議**', '').strip()


        else:


            summary = summary_part.strip()





        # 提取參考依據


        if has_ref_section and len(parts) > 1:


            ref_part = parts[1].strip()


            ref_pattern = r'《([^》]+)》\s*(.*?)(?=《|$)'


            matches = re.finditer(ref_pattern, ref_part, re.DOTALL)





            for match in matches:


                filename = match.group(1).strip()


                content = match.group(2).strip()


                page_match = re.search(r'\(頁碼[：:]\s*([^)]+)\)', content)


                page = page_match.group(1) if page_match else None


                if page_match:


                    content = content.replace(page_match.group(0), '').strip()





                if content:


                    references.append(ReferenceSource(


                        filename=filename,


                        content=content,


                        page=page


                    ))





        return cls(


            summary=summary,


            references=references,


            query_type=query_type


        )

