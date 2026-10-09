import concurrent.futures
import json
import os
from google import genai
from google.cloud import storage
from google.genai import types
from pitchgen_utils.gcs_util import read_gcs_file
from agents.workflows.base_workflow import BaseWorkflow


class DetectedLanguage:
  def __init__(self, language_code, confidence=1.0):
    self.language_code = language_code
    self.confidence = confidence


class SlideTranslator:
  """Class for translating slides, migrated and adapted for ADK 2.0."""

  def __init__(self, config):
    self.config = config
    self.__project_name = self.config['default']['project_name']
    self.__location = 'global'
    self.__gemini_model = self.config['default']['gemini_model']
    self.storage_client = storage.Client()
    self.translation_bucket_name = self.config['bucket']['content']
    self.translation_bucket = self.storage_client.bucket(
        self.translation_bucket_name
    )
    self.target_lang_code = ''
    self.translate_instructions = ''

    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Load example translations from GCS
    examples_gcs_path = f'gs://{self.translation_bucket_name}/translation_data/model_examples/example_translations.json'
    try:
      trans_data = read_gcs_file(
          examples_gcs_path, project_id=self.__project_name
      )
      self.trans_dict = json.loads(trans_data)
    except Exception as e:
      print(
          'Warning: Failed to load translation examples from GCS'
          f' ({examples_gcs_path}): {e}'
      )
      self.trans_dict = {}

    # Load prompt template
    prompt_path = os.path.join(
        current_dir, 'prompt_templates', 'translate_chunks.txt'
    )
    with open(prompt_path, 'r') as f:
      self.trans_chunks_prompt = f.read()

    # Load language code mappings
    config_path = os.path.join(current_dir, 'config', 'translate.json')
    with open(config_path, 'r') as f:
      mappings = json.loads(f.read())
    self.codeToLang = mappings['codeToLang']
    self.langToCode = mappings['langToCode']

  def detect_language(self, sentence):
    client = genai.Client(
        vertexai=True, project=self.__project_name, location='global'
    )
    prompt = (
        "Analyze the following text and determine its language.\n"
        "Return ONLY the ISO 639-1 language code (e.g., 'en', 'de', 'es', 'zh-TW', 'zh-CN', 'ja').\n"
        "Do not include any explanation or other text.\n\n"
        f"Text: {sentence}"
    )
    try:
      response = client.models.generate_content(
          model=self.__gemini_model,
          contents=[prompt],
          config=types.GenerateContentConfig(
              temperature=0.0,
          ),
      )
      lang_code = (response.text or "").strip().lower()
      for code in self.codeToLang.keys():
        if code.lower() == lang_code:
          return DetectedLanguage(code, 1.0)
      return DetectedLanguage(lang_code, 1.0)
    except Exception as e:
      print(f"[SlideTranslator] Gemini language detection failed: {e}")
      return DetectedLanguage("en", 1.0)

  def get_translation_data(self, raw_data):
    cnt = 1
    idDict = dict()
    sentDict = dict()
    slideData = dict()
    for slideId in raw_data.keys():
      slideData[slideId] = {'text': '', 'ids': set()}
      for shapeId in raw_data[slideId]['shapes'].keys():
        for key in raw_data[slideId]['shapes'][shapeId].keys():
          temp = slideId + '@' + shapeId + '@' + key
          text = ''.join(
              s
              for s in raw_data[slideId]['shapes'][shapeId][key]['Text']
              if s.isalnum()
          )

          if text and (not text.isdigit()):
            slideData[slideId]['ids'].add(str(cnt))
            slideData[slideId]['text'] += (
                raw_data[slideId]['shapes'][shapeId][key]['Text'] + ' '
            )
            if str(cnt) in idDict.keys():
              idDict[str(cnt)].append(temp)
              sentDict[str(cnt)] += raw_data[slideId]['shapes'][shapeId][key][
                  'Text'
              ]
            else:
              idDict[str(cnt)] = [] + [temp]
              sentDict[str(cnt)] = raw_data[slideId]['shapes'][shapeId][key][
                  'Text'
              ]

            if raw_data[slideId]['shapes'][shapeId][key]['Text'].endswith('\n'):
              cnt = cnt + 1
          else:
            if str(cnt) in idDict.keys():
              cnt = cnt + 1
        if str(cnt) in idDict.keys():
          cnt = cnt + 1

      cnt = len(idDict.keys()) + 1
      for shapeId in raw_data[slideId]['tables'].keys():
        for cellId in raw_data[slideId]['tables'][shapeId].keys():
          for key in raw_data[slideId]['tables'][shapeId][cellId].keys():
            temp = slideId + '@' + shapeId + '@' + cellId + '@' + key
            text = ''.join(
                s
                for s in raw_data[slideId]['tables'][shapeId][cellId][key][
                    'Text'
                ]
                if s.isalnum()
            )

            if text and (not text.isdigit()):
              slideData[slideId]['ids'].add(str(cnt))
              slideData[slideId]['text'] += (
                  raw_data[slideId]['tables'][shapeId][cellId][key]['Text']
                  + ' '
              )
              if str(cnt) in idDict.keys():
                idDict[str(cnt)].append(temp)
                sentDict[str(cnt)] += raw_data[slideId]['tables'][shapeId][
                    cellId
                ][key]['Text']
              else:
                idDict[str(cnt)] = [] + [temp]
                sentDict[str(cnt)] = raw_data[slideId]['tables'][shapeId][
                    cellId
                ][key]['Text']

              if raw_data[slideId]['tables'][shapeId][cellId][key][
                  'Text'
              ].endswith('\n'):
                cnt = cnt + 1
            else:
              if str(cnt) in idDict.keys():
                cnt = cnt + 1
          if str(cnt) in idDict.keys():
            cnt = cnt + 1

    for slideId in slideData.keys():
      if slideData[slideId]['text']:
        lang = self.detect_language(slideData[slideId]['text'])
        if lang.confidence >= 0.85:
          slideData[slideId]['lang'] = lang.language_code

    multi_lang_data = dict()
    multi_lang_ind = dict()
    for slideId in slideData.keys():
      if 'lang' in slideData[slideId].keys():
        lang = slideData[slideId]['lang']
        if lang not in multi_lang_ind.keys():
          multi_lang_data[lang] = {
              'source': lang,
              'idDict': dict(),
              'sentDict': dict(),
          }
          multi_lang_ind[lang] = 1
        for elemId in slideData[slideId]['ids']:
          multi_lang_data[lang]['idDict'][str(multi_lang_ind[lang])] = idDict[
              elemId
          ]
          multi_lang_data[lang]['sentDict'][str(multi_lang_ind[lang])] = (
              sentDict[elemId]
          )
          multi_lang_ind[lang] += 1

    return multi_lang_data

  def get_translation_batches(self, num_batches, translation_data):
    batch_size = len(translation_data[0]) // num_batches
    lines_limit = (
        10
        if self.target_lang_code in ['ja', 'ko', 'zh-TW', 'zh-CN', 'el', 'th']
        else 30
    )
    while batch_size > lines_limit:
      num_batches += 1
      batch_size = len(translation_data[0]) // num_batches

    batches = []
    inpcnt = 1
    for val in range(num_batches):
      cnt = 1
      idBatch = dict()
      sentBatch = dict()
      while cnt <= batch_size:
        idBatch[str(cnt)] = translation_data[0][str(inpcnt)]
        sentBatch[str(cnt)] = translation_data[1][str(inpcnt)]
        cnt += 1
        inpcnt += 1
      batches.append([idBatch, sentBatch])

    cnt = 1
    idBatch = dict()
    sentBatch = dict()
    while inpcnt <= len(translation_data[0]):
      idBatch[str(cnt)] = translation_data[0][str(inpcnt)]
      sentBatch[str(cnt)] = translation_data[1][str(inpcnt)]
      cnt += 1
      inpcnt += 1

    if cnt > 1:
      batches.append([idBatch, sentBatch])

    return batches

  def fetch_translate_examples(self, src_lang_code):
    ex_data = []
    if {src_lang_code, self.target_lang_code}.issubset(
        set(self.trans_dict.keys())
    ):
      ex_lens = [3, 8, 4, 6]
      cnt = 1
      for val in ex_lens:
        inp = dict()
        out = dict()
        for ind in range(1, val + 1):
          inp[str(ind)] = self.trans_dict[src_lang_code][str(cnt)]
          out[str(ind)] = self.trans_dict[self.target_lang_code][str(cnt)]
          cnt += 1
        ex_data.append((inp, out))
    return ex_data

    custom_rule = (
        '\n            8. ADDITIONAL USER TRANSLATION INSTRUCTIONS / GLOSSARY:'
        f' {self.translate_instructions}'
        if getattr(self, 'translate_instructions', '')
        else ''
    )
    prompt = [
        f"""You are an expert in translating {src_lang} content to {tar_lang} language while preserving the original meaning and context.
            You follow the RULES below VERY STRICTLY:
            1. DO NOT translate Google Cloud Product names, Technical Terms (acronyms), Organization names.
            2. DO NOT translate any escape sequences like '\\n', '\\t', etc., which may appear in the input text.
            3. DO NOT translate numerical values, special characters like '%', '.', etc., and whitespaces.
            4. Wherever required, please USE ONLY VALID escape sequences.
            5. Ensure that the translation is accurate and fluent, it should retain the actual meaning, sentence structure and context as much as possible.
            6. Pay attention to gender agreement for articles and adjectives, nuances, idioms, and cultural context to provide the best possible translation.
            7. Please output ONLY VALID JSON object.{custom_rule}"""
    ]
    if examples:
      prompt.extend([
          """<input>""",
          json.dumps(examples[0][0]),
          """</input>
                <output>""",
          json.dumps(examples[0][1]),
          """</output>

                <input>""",
          json.dumps(examples[1][0]),
          """</input>
                <output>""",
          json.dumps(examples[1][1]),
          """</output>

                <input>""",
          json.dumps(examples[2][0]),
          """</input>
                <output>""",
          json.dumps(examples[2][1]),
          """</output>

                <input>""",
          json.dumps(examples[3][0]),
          """</input>
                <output>""",
          json.dumps(examples[3][1]),
          """</output>""",
      ])

    prompt.extend([
        """<input>""",
        json.dumps(input_text),
        """</input>
            <output>""",
    ])
    return prompt

  def getTranslationChunkPrompt(self, input_chunks):
    prompt = [
        self.trans_chunks_prompt,
        json.dumps(input_chunks),
        """
            </input>
            <output>
            """,
    ]
    return prompt

  def get_translated_text(self, batch):
    trans_examples = self.fetch_translate_examples(batch[2])
    inpPrompt = self.getTranslationPrompt(
        self.codeToLang[batch[2]],
        self.codeToLang[self.target_lang_code],
        trans_examples,
        batch[1],
    )

    retry = 0
    flag = 0
    output_data = {}
    while True:
      try:
        client = genai.Client(
            vertexai=True, project=self.__project_name, location='global'
        )

        response = client.models.generate_content(
            model=self.__gemini_model,
            contents=inpPrompt,
            config=types.GenerateContentConfig(
                system_instruction='Please provide output in json format.',
                response_mime_type='application/json',
                temperature=0,
            ),
        )
        output = ''
        if not response.candidates:
          output = ''
        else:
          content = response.candidates[0].content
          if not content or not content.parts:
            output = ''
          else:
            output = ''.join([
                part.text
                for part in content.parts
                if hasattr(part, 'text') and part.text
            ])

        result = output.split('<output>')[-1]
        if self.target_lang_code in ['ja', 'ko', 'zh-TW', 'zh-CN', 'el', 'th']:
          json_res = (
              result[result.index('{') : len(result) - result[::-1].index('}')]
              .encode('raw_unicode_escape')
              .decode('utf_8')
          )
        else:
          json_res = (
              result[result.index('{') : len(result) - result[::-1].index('}')]
              .encode()
              .decode()
          )

        output_data = json.loads(json_res, strict=False)
        flag = 1
        if flag:
          break
      except Exception as e:
        print(e)
        if retry:
          retry -= 1
          continue
        else:
          print('single translation failed')
          break

    translation_result = dict()
    entries = batch[0].keys()
    for ent in entries:
      font_offset = 0
      inp_str = batch[1][ent].strip()
      op_str = output_data.get(ent, inp_str).strip()
      if len(op_str) > len(inp_str):
        font_offset = round(((len(op_str) - len(inp_str)) / len(inp_str)) * 2)

      if len(batch[0][ent]) == 1:
        translation_result[batch[0][ent][0]] = [op_str, font_offset]
      else:
        translation_result[tuple(batch[0][ent])] = [op_str, font_offset]

    return translation_result

  def get_translated_chunks(self, batch):
    ind = 1
    slide_data = dict()
    model_data = dict()
    for val in batch:
      slide_data[str(ind)] = val
      model_data[str(ind)] = {
          'text': val[1][0],
          'chunks': [chunk['Text'] for chunk in val[2]],
      }
      ind += 1

    inpPrompt = self.getTranslationChunkPrompt(model_data)
    retry = 0
    flag = 0
    output_data = {}
    while True:
      try:
        client = genai.Client(
            vertexai=True, project=self.__project_name, location='global'
        )

        response = client.models.generate_content(
            model=self.__gemini_model,
            contents=inpPrompt,
            config=types.GenerateContentConfig(
                system_instruction='Please provide output in json format.',
                response_mime_type='application/json',
                max_output_tokens=28000,
                temperature=0,
            ),
        )
        output = ''
        if not response.candidates:
          output = ''
        else:
          content = response.candidates[0].content
          if not content or not content.parts:
            output = ''
          else:
            output = ''.join([
                part.text
                for part in content.parts
                if hasattr(part, 'text') and part.text
            ])
        result = output.split('<output>')[-1]

        if self.target_lang_code in ['ja', 'ko', 'zh-TW', 'zh-CN', 'el', 'th']:
          json_res = (
              result[result.index('{') : len(result) - result[::-1].index('}')]
              .encode('raw_unicode_escape')
              .decode('utf_8')
          )
        else:
          json_res = (
              result[result.index('{') : len(result) - result[::-1].index('}')]
              .encode()
              .decode()
          )

        output_data = json.loads(json_res, strict=False)
        flag = 1
        if flag:
          break
      except Exception as e:
        print(e)
        if retry:
          retry -= 1
          continue
        else:
          print('chunk translation failed')
          break

    out_entries = output_data.keys()
    for ent in out_entries:
      nf_chunks = []
      f_chunks = []
      for val in output_data[ent]:
        if val['in-text']:
          trans_text = model_data[ent]['text'].replace(' ', '')
          orig_text = val['in-text'].replace(' ', '')
          val['position'] = trans_text.find(orig_text)
          if val['position'] < 0:
            nf_chunks.append(val)
          else:
            val['in-text'] = val['in-text'].strip()
            f_chunks.append(val)
        else:
          nf_chunks.append(val)

      output_data[ent] = {
          'not_found': nf_chunks,
          'found': sorted(f_chunks, key=lambda x: x['position']),
      }

    final_data = dict()
    for ent in out_entries:
      unq_id = slide_data[ent][0]
      final_data[unq_id] = dict()
      visited = slide_data[ent][3]
      rem_ind = set()
      for val in output_data[ent]['not_found']:
        for j in range(len(slide_data[ent][2])):
          if val['given'] == slide_data[ent][2][j]['Text']:
            final_data[unq_id][visited[j]] = slide_data[ent][2][j]
            final_data[unq_id][visited[j]]['FontSize'] -= slide_data[ent][1][1]
            rem_ind.add(j)
            break

      slide_temp = []
      visited_temp = []
      for j in range(len(slide_data[ent][2])):
        if j not in rem_ind:
          slide_temp.append(slide_data[ent][2][j])
          visited_temp.append(visited[j])

      slide_data[ent][2] = slide_temp
      visited = visited_temp
      visited.sort(reverse=True)

      for val in output_data[ent]['found']:
        for inp_chunk in slide_data[ent][2]:
          if val['given'] == inp_chunk['Text']:
            if inp_chunk['Text'] and val['in-text']:
              if (inp_chunk['Text'][0] != val['in-text'][0]) and inp_chunk[
                  'Text'
              ][0].isspace():
                spList = []
                for s in inp_chunk['Text']:
                  if s.isspace():
                    spList.append(s)
                  else:
                    break
                val['in-text'] = ''.join(spList) + val['in-text']
              if (inp_chunk['Text'][-1] != val['in-text'][-1]) and inp_chunk[
                  'Text'
              ][-1].isspace():
                spList = []
                for s in inp_chunk['Text'][::-1]:
                  if s.isspace():
                    spList.append(s)
                  else:
                    break
                val['in-text'] = val['in-text'] + ''.join(spList[::-1])

            temp = inp_chunk.copy()
            temp['Text'] = val['in-text']
            temp['FontSize'] -= slide_data[ent][1][1]
            final_data[unq_id][visited.pop()] = temp
            break

    return final_data

  def translate_texts(self, lang_data):
    slideIds = []
    for val in lang_data['idDict'].values():
      if len(val) > 1:
        slideIds.extend([ids.split('@')[0] for ids in val])
      else:
        slideIds.append(val[0].split('@')[0])
    num_slides = len(set(slideIds))
    print(
        f"No. of {self.codeToLang[lang_data['source']]} slides to translate:"
        f' {num_slides}'
    )

    num_batches = 1
    if num_slides in range(6, 11):
      num_batches = 2
    elif num_slides in range(11, 21):
      num_batches = 3
    else:
      num_batches = 4

    batches = self.get_translation_batches(
        num_batches, [lang_data['idDict'], lang_data['sentDict']]
    )
    for batch in batches:
      batch.append(lang_data['source'])

    with concurrent.futures.ThreadPoolExecutor() as executor:
      futures = [
          executor.submit(self.get_translated_text, batch) for batch in batches
      ]

    translated_text_op = []
    for future in futures:
      try:
        result = future.result()
        translated_text_op.append(result)
      except Exception as e:
        print(e)
        continue

    return translated_text_op

  def process_translate_io(self, uiInp):
    print('you are now in translation module')
    translate_data = read_gcs_file(uiInp, project_id=self.__project_name)
    translate_dict = json.loads(translate_data)
    input_data = translate_dict[translate_dict['presentationId']]
    target_lang = translate_dict['targetLanguage']
    print('target language: ', target_lang)
    self.target_lang_code = self.langToCode[target_lang]
    self.translate_instructions = str(
        translate_dict.get('translateInstructions')
        or translate_dict.get('translate_instructions')
        or ''
    ).strip()
    if self.translate_instructions:
      print('translate instructions: ', self.translate_instructions)

    lang_data = self.get_translation_data(input_data)
    detected_langs = set(lang_data.keys())
    translate_langs = detected_langs.difference({self.target_lang_code})
    print(f'Detected languages: {detected_langs}')
    print(f'Translation to be done on: {translate_langs}')

    if translate_langs:
      lang_batches = [lang_data[lang] for lang in translate_langs]

      with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(self.translate_texts, batch)
            for batch in lang_batches
        ]

      translate_texts_op = []
      for future in futures:
        try:
          result = future.result()
          translate_texts_op.extend(result)
        except Exception as e:
          print(e)
          continue

      ready_data = []
      chunks_to_process = []
      for batch_op in translate_texts_op:
        entries = batch_op.keys()
        for ent in entries:
          if isinstance(ent, tuple):
            chunks_to_process.append([ent, batch_op[ent]])
          else:
            ready_data.append([ent, batch_op[ent]])

      chunk_process_data = []
      for chunk_ent in chunks_to_process:
        ent_id = chunk_ent[0][0]
        ent_id_split = ent_id.split('@')
        chunks_pos = [chunk_id.split('@')[-1] for chunk_id in chunk_ent[0]]
        if len(ent_id_split) == 3:
          text_chunks = [
              input_data[ent_id_split[0]]['shapes'][ent_id_split[1]][pos]
              for pos in chunks_pos
          ]
          chunks_entry = [
              '@'.join(ent_id_split[:2]),
              chunk_ent[1],
              text_chunks,
              chunks_pos,
          ]
        else:
          text_chunks = [
              input_data[ent_id_split[0]]['tables'][ent_id_split[1]][
                  ent_id_split[2]
              ][pos]
              for pos in chunks_pos
          ]
          chunks_entry = [
              '@'.join(ent_id_split[:3]),
              chunk_ent[1],
              text_chunks,
              chunks_pos,
          ]
        chunk_process_data.append(chunks_entry)

      num_chunks = (
          5
          if self.target_lang_code in ['ja', 'ko', 'zh-TW', 'zh-CN', 'el', 'th']
          else 10
      )
      chunk_batches = [
          chunk_process_data[x : x + num_chunks]
          for x in range(0, len(chunk_process_data), num_chunks)
      ]
      with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(self.get_translated_chunks, batch)
            for batch in chunk_batches
        ]

      chunks_op = []
      for future in futures:
        try:
          result = future.result()
          chunks_op.append(result)
        except Exception as e:
          print(e)
          continue

      for val in ready_data:
        id_split = val[0].split('@')
        if len(id_split) == 3:
          temp = input_data[id_split[0]]['shapes'][id_split[1]][id_split[2]][
              'Text'
          ]
        else:
          temp = input_data[id_split[0]]['tables'][id_split[1]][id_split[2]][
              id_split[3]
          ]['Text']

        if temp and val[1][0]:
          if (temp[0] != val[1][0][0]) and temp[0].isspace():
            spList = []
            for s in temp:
              if s.isspace():
                spList.append(s)
              else:
                break
            val[1][0] = ''.join(spList) + val[1][0]
          if (temp[-1] != val[1][0][-1]) and temp[-1].isspace():
            spList = []
            for s in temp[::-1]:
              if s.isspace():
                spList.append(s)
              else:
                break
            val[1][0] = val[1][0] + ''.join(spList[::-1])

        if len(id_split) == 3:
          input_data[id_split[0]]['shapes'][id_split[1]][id_split[2]][
              'Text'
          ] = val[1][0]
          input_data[id_split[0]]['shapes'][id_split[1]][id_split[2]][
              'FontSize'
          ] -= val[1][1]
        else:
          input_data[id_split[0]]['tables'][id_split[1]][id_split[2]][
              id_split[3]
          ]['Text'] = val[1][0]
          input_data[id_split[0]]['tables'][id_split[1]][id_split[2]][
              id_split[3]
          ]['FontSize'] -= val[1][1]

      for val in chunks_op:
        entries = val.keys()
        for ent in entries:
          chunks = val[ent].keys()
          id_split = ent.split('@')
          for chunk in chunks:
            try:
              if len(id_split) == 2:
                input_data[id_split[0]]['shapes'][id_split[1]][chunk] = val[
                    ent
                ][chunk]
              else:
                input_data[id_split[0]]['tables'][id_split[1]][id_split[2]][
                    chunk
                ] = val[ent][chunk]
            except:
              print(id_split)
              continue

      translate_dict[translate_dict['presentationId']] = input_data
      res_filename = (
          'translation_data/'
          + ''.join(uiInp.split('/')[-1].split('_')[:-1])
          + '_Response.json'
      )
      print('res_filename: ', res_filename)
      blob = self.translation_bucket.blob(res_filename)
      blob.upload_from_string(
          json.dumps(translate_dict, indent=2), content_type='application/json'
      )
      result_filename = (
          f"gs://{self.config['bucket']['content']}/{res_filename}"
      )

      return result_filename
    else:
      print('Source language and Target language are the same')
      return uiInp


class TranslationWorkflow(BaseWorkflow):
  """Skill to perform asynchronous slide translation via GCS payloads."""

  def __init__(self, config):
    super().__init__(
        'TranslationWorkflow',
        'Translates Google Slides text content while preserving complex'
        ' styles.',
    )
    self.config = config
    self.translator = SlideTranslator(config)

  def execute(self, request_file_url: str) -> str:
    """Executes the translation workflow.

    Args:
        request_file_url: GCS path to the input translation JSON payload.

    Returns:
        GCS path to the translated response JSON payload.
    """
    try:
      result_file_url = self.translator.process_translate_io(request_file_url)
      return result_file_url
    except Exception as e:
      print(f'[TranslationWorkflow] Error during execution: {e}')
      raise e
