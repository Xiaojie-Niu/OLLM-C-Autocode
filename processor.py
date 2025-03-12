import os
import json
import time
import http.client
from typing import List, Dict, Tuple, Optional, Callable
import pandas as pd
import numpy as np

class TextProcessor:
    """文本处理类，处理编码和校准逻辑"""
    def __init__(self, api_settings: dict, progress_callback: Callable[[int, int], None]):
        self.base_url = api_settings['base_url']
        self.api_key = api_settings['api_key']
        self.model = api_settings.get('model', 'gpt-4o-all')
        self.progress_callback = progress_callback
        self.preview_callback = None  # 新增预览回调
        self.delay_seconds = 3  # 设置默认延时为3秒，可以根据需要调整

    def set_preview_callback(self, callback: Callable[[str, str, str], None]):
        """设置预览回调函数"""
        self.preview_callback = callback
        
    def set_delay_seconds(self, seconds: int):
        """设置延时秒数"""
        self.delay_seconds = seconds

    def read_excel_data(self, file_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
        """读取Excel文件中的数据"""
        try:
            xl = pd.ExcelFile(file_path)
            available_sheets = xl.sheet_names
            
            if 'Coding Results' not in available_sheets:
                raise ValueError("Required sheet 'Coding Results' not found")
            if 'code' not in available_sheets:
                raise ValueError("Required sheet 'code' not found")
                
            coding_results = xl.parse('Coding Results')
            code_df = xl.parse('code')
            
            notes = []
            note_sheet_name = next((s for s in available_sheets 
                                  if s.lower() in ['note', 'notes']), None)
            
            if note_sheet_name:
                note_df = xl.parse(note_sheet_name, header=None)
                notes = [str(note) for note in note_df[0] 
                        if pd.notna(note) and str(note).strip()]
                
            return coding_results, code_df, notes
            
        except Exception as e:
            raise Exception(f"Error reading Excel file: {str(e)}")

    def generate_prompt(self, code_df: pd.DataFrame, notes: List[str], text: str) -> str:
        """生成提示词"""
        valid_codes = [row['code_num'] for _, row in code_df.iterrows() 
                      if row['code_num'] != 'f']
        valid_codes.sort()
        
        prompt = (
            "你是一位经验丰富的教育研究编码专家，专门从事中文在线学习文本的编码工作。\n"
            f"在本任务中，你需要将文本分类为{len(valid_codes)}个类别之一，"
            f"可选编码为：{', '.join(valid_codes)}。\n\n"
        )
        
        prompt += "编码框架：\n"
        for _, row in code_df.iterrows():
            if row['code_num'] != 'f':
                prompt += f"\n编码 {row['code_num']} - {row['code']}:\n"
                prompt += f"定义：{row['explain']}\n"
                prompt += f"示例：{row['example']}\n"
        
        if notes:
            prompt += "\n校准说明：\n"
            for note in notes:
                prompt += f"- {note}\n"
        
        prompt += f"\n待编码文本：{text}\n"
        prompt += f"\n你只需要返回编码的字符类别，只输出字母，不要返回任何其他的解释！\n"
        return prompt

    def call_model(self, prompt: str, timeout: float = 10.0) -> str:
        """调用API获取模型响应"""
        host = self.base_url.replace("https://", "").replace("http://", "").rstrip("/")
        
        messages = [{"role": "system", "content": prompt}]
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0.1
        })
        
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            conn = http.client.HTTPSConnection(host, timeout=timeout)
            conn.request("POST", "/v1/chat/completions", payload, headers)
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    res = conn.getresponse()
                    data = json.loads(res.read().decode("utf-8"))
                    return data['choices'][0]['message']['content'].strip().lower()
                except Exception:
                    if time.time() - start_time >= timeout:
                        return 'o'
                    raise
            
            return 'o'
            
        except Exception as e:
            raise Exception(f"API call error: {str(e)}")
        finally:
            try:
                conn.close()
            except:
                pass

    def process_file(self, file_path: str, save_path: str, mode: str, custom_prompt: Optional[str] = None) -> Dict:
        """处理文件并保存结果"""
        try:
            coding_results, code_df, notes = self.read_excel_data(file_path)
            
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_file = os.path.join(save_path, f"{base_name}_{mode}_{timestamp}.xlsx")
            
            total_items = len(coding_results)
            results = {
                'processed': 0,
                'correct': 0,
                'total': total_items,
                'start_time': time.time(),
                'detailed_results': [],
                'save_file': save_file,
                'realtime_outputs': []  # 添加实时输出列表
            }
            
            result_df = coding_results.copy()
            codes = []
            detailed_results = []
            
            for idx, (text, human_code) in enumerate(
                zip(coding_results['text'], 
                    coding_results['hcode'] if mode == 'calibrate' else [None] * total_items)
            ):
                self.progress_callback(idx + 1, total_items)
                
                # 准备实时输出信息
                display_text = text[:50] + "..." if len(text) > 50 else text
                realtime_output = [f"\n文本 {idx + 1}/{total_items}:", f"内容: {display_text}"]
                
                try:
                    if custom_prompt:
                        # 替换自定义提示词中的[文本]占位符
                        prompt = custom_prompt.replace("[文本]", text)
                    else:
                        prompt = self.generate_prompt(code_df, notes, text)
                    
                    # 在调用模型前更新预览，显示"处理中..."
                    if self.preview_callback:
                        self.preview_callback(
                            prompt, 
                            human_code if mode == 'calibrate' else "N/A", 
                            "处理中..."
                        )
                    
                    code = self.call_model(prompt)
                    codes.append(code)
                    
                    # 在获得模型回复后更新预览
                    if self.preview_callback:
                        self.preview_callback(
                            prompt, 
                            human_code if mode == 'calibrate' else "N/A", 
                            code
                        )
                    
                    result_item = {
                        'index': idx + 1,
                        'text': text,
                        'model_code': code,
                        'display_text': display_text
                    }
                    
                    if mode == 'calibrate':
                        result_item['human_code'] = human_code
                        result_item['correct'] = code == human_code
                        if code == human_code:
                            results['correct'] += 1
                        
                        # 添加校准模式的额外输出信息
                        realtime_output.extend([
                            f"人工编码: {human_code}",
                            f"模型编码: {code}",
                            f"结果: {'✓' if code == human_code else '✗'}"
                        ])
                    else:
                        realtime_output.extend([
                            f"模型编码: {code}"
                        ])
                    
                    detailed_results.append(result_item)
                    
                    # 延长延时时间，让用户有更多时间查看结果
                    time.sleep(self.delay_seconds)
                    
                except Exception as e:
                    codes.append('o')
                    error_msg = str(e)
                    result_item = {
                        'index': idx + 1,
                        'text': text,
                        'model_code': 'o',
                        'error': error_msg,
                        'display_text': display_text
                    }
                    detailed_results.append(result_item)
                    realtime_output.append(f"错误: {error_msg}")
                    
                    # 在发生错误时更新预览
                    if self.preview_callback:
                        self.preview_callback(
                            prompt if 'prompt' in locals() else "加载提示词出错", 
                            human_code if mode == 'calibrate' else "N/A", 
                            f"错误: {error_msg}"
                        )
                    
                    # 错误后也延长延时
                    time.sleep(self.delay_seconds)
                
                # 保存实时输出
                results['realtime_outputs'].append(realtime_output)
                results['processed'] += 1

            # 计算结果
            results['time'] = time.time() - results['start_time']
            if mode == 'calibrate':
                results['accuracy'] = results['correct'] / total_items
            
            # 保存到Excel
            result_df['model_code'] = codes
            if mode == 'calibrate':
                result_df['is_correct'] = [r.get('correct', False) for r in detailed_results]
            
            with pd.ExcelWriter(save_file, engine='openpyxl') as writer:
                code_df.to_excel(writer, sheet_name='code', index=False)
                result_df.to_excel(writer, sheet_name='Coding Results', index=False)
                
                stats_df = pd.DataFrame([{
                    '处理时间': f"{results['time']:.1f}秒",
                    '总条数': total_items,
                    '处理条数': results['processed'],
                    '准确率': f"{results['accuracy']:.2%}" if 'accuracy' in results else 'N/A'
                }])
                stats_df.to_excel(writer, sheet_name='Statistics', index=False)
                
                pd.DataFrame(detailed_results).to_excel(
                    writer, 
                    sheet_name='Detailed Results',
                    index=False
                )
            
            results['detailed_results'] = detailed_results
            return results
            
        except Exception as e:
            raise Exception(f"Processing error: {str(e)}")
