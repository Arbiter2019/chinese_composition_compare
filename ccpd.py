## Chinese composition plagiarism detection(chater level)
import re
import numpy as np
from difflib import SequenceMatcher
import jieba

def essay_overlap_analysis(text1, text2, threshold=0.85):
    """
    对比两篇作文的重复率（支持句子级别、分词级别）

    参数:
        text1: str 第一篇作文（作为基准）
        text2: str 第二篇作文
        threshold: float 相似度阈值，超过则视为重复

    返回:
        dict 包含：
            sentence_repeat_rate: float 句子层面重复率
            word_repeat_rate: float 分词层面重复率
            details: list 每个句子的比对详情
    """

    def split_sentences(text):
        """中文句子切分"""
        sentence_end_pattern = r"[。！？；:：.!?;…]+"
        sentences = re.split(sentence_end_pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def similarity_ratio(a, b):
        """字符串相似度"""
        return SequenceMatcher(None, a, b).ratio()

    def word_overlap_ratio(a, b):
        """基于分词的重叠率"""
        words_a = set(jieba.cut(a))
        words_b = set(jieba.cut(b))
        if not words_a or not words_b:
            return 0
        return len(words_a & words_b) / len(words_a | words_b)

    # 按句子切分
    sentences1 = split_sentences(text1)
    sentences2 = split_sentences(text2)

    details = []
    repeated_sentences = 0
    word_scores = []

    for s1 in sentences1:
        if not sentences2:
            best_sentence_score = 0
            best_word_score = 0
            best_match = ""
        else:
            # 句子级相似度
            sentence_scores = [similarity_ratio(s1, s2) for s2 in sentences2]
            best_sentence_score = max(sentence_scores)
            best_match = sentences2[np.argmax(sentence_scores)]

            # 分词级相似度
            word_scores_list = [word_overlap_ratio(s1, s2) for s2 in sentences2]
            best_word_score = max(word_scores_list)

        is_repeated = best_sentence_score >= threshold
        if is_repeated:
            repeated_sentences += 1

        word_scores.append(best_word_score)

        details.append({
            "sentence": s1,
            "best_match": best_match,
            "sentence_score": best_sentence_score,
            "word_score": best_word_score,
            "is_repeated": is_repeated
        })

    sentence_repeat_rate = repeated_sentences / len(sentences1) if sentences1 else 0
    symmetry_rate =  2* repeated_sentences / (len(sentences1)+len(sentences2)) if (sentences1 or sentences2) else 0
    word_repeat_rate = np.mean(word_scores) if word_scores else 0

    return {
        "sentence_repeat_rate": sentence_repeat_rate,
        "word_repeat_rate": word_repeat_rate,
        "symmetry_rate":symmetry_rate,
        "details": details
    }


# 示例
def main():
    text1 = "“让我们恭喜以上同学成功入团！”热烈的掌声响起，我扯出一抹微笑为同学们喝彩，可那笑却如纸糊的一般，心底的失落像冰冷的潮水，无声地漫上来。那一次次面对机会，因胆怯迟迟不敢举起的手，正是我与他们之间最遥远的距离。放学后，我垂着头走在回家路上，路过熟悉的小区花园，一束明亮的阳光忽然抓住我的视线。它不像寻常阳光散漫铺洒，反倒像一盏聚光灯，直直笼罩着花园里一个角落的绿植，与周遭的深绿形成鲜明对比。花园不大，几株玉兰、几丛灌木，便是全部景致。可那个角落的所有叶片竟都倾斜着拼命伸展，全力迎向光源。阳光穿透叶片，叶脉如金色血管，涌动着生命的渴望。我从未想过，这片平淡的小天地里，竟藏着如此执着的坚守。那束光珍贵又短暂，或许一日仅有一刻钟，可植物们始终蓄力等待，抓住光亮奋力生长，光走后也默默积蓄力量，静待下一次机遇。草木尚知向阳而生，我又怎能一味怯懦？我想起那个上课怕答错而低头的自己，那个遇难题不敢请教老师的自己，那个面对入团机会因惧败退缩的自己，多少机会就在犹豫中悄然溜走。不久，阳光偏移离去，角落绿植重回平淡，可我知道，它们早已抓住机遇，攒足了生长的力量。那个午后，那束穿透角落的光，那些无声向上的叶，让我明白：努力争取，从来不是目标的注脚，而是过程本身。机会，总会偏爱那些时刻准备着，并敢于用尽全部力气去靠近它的生命。人生没有白费的努力，唯有勇敢迈步，才能抓住稍纵即逝的机遇。从那天起，我卸下胆怯，勇敢改变。课堂上，我鼓起勇气举手发言，不再怕回答有误；学习遇到困难，我主动找老师请教，不再独自纠结；班级活动，我积极报名参与，不再因怕出错而旁观。我学着像那小花园中的绿植，主动向着光的方向靠拢。数月后的第二次入团报名，我不再犹豫，高高举起了手。我知道竞争依旧激烈，或许仍会失败，但纵然如此又何妨，勇敢迈出争取的一步，本就是一种成长。如今再逛小花园，那些叶片向阳的模样，早已刻进心底。它们教会我的，不仅是抓住机遇的道理，更是直面怯懦、勇敢向前的勇气。"
    text2 = "“让我们恭喜以上同学成功入团!”热烈的掌声响起,我由衷为同学喝彩,心底却藏着难以言说的失落。那一次次面对机会,因胆怯迟迟不敢举起的手,正是我与他们之间最遥远的距离。放学后,我垂着头走在回家路上,路过熟悉的小区花园,一束明亮的阳光忽然抓住我的视线。它不像寻常阳光散漫铺洒,反倒像一盏聚光灯,直直笼罩着花园里一个角落的绿植,与周遭的深绿形成鲜明对比。花园不大,几株玉兰、几丛灌木,便是全部景致。可那个角落的所有叶片竟都倾斜着拼命伸展,全力迎向光源。阳光穿透叶片,叶脉如金色血管,涌动着生命的渴望。我从未想过,这片平淡的小天地里,竟藏着如此执着的坚守。那束光珍贵又短暂,或许一日仅有一刻钟,可植物们始终蓄力等待,抓住光亮奋力生长,光走后也默默积蓄力量,静待下一次机遇。草木尚知向阳而生,我又怎能一味怯懦?我想起那个上课怕答错而低头的自己,那个遇难题不敢请教老师的自己,那个面对入团机会因惧败退缩的自己,多少机会就在犹豫中悄然溜走。不久,阳光偏移离去,角落绿植重回平淡,可我知道,它们早已抓住机遇,攒足了生长的力量。那个午后,那束穿透角落的光,那些无声向上的叶,让我明白:努力争取,从来不是目标的注脚,而是过程本身。机会,总会偏爱那些时刻准备着,并敢于用尽全部力气去靠近它的生命。人生没有白费的努力,唯有勇敢迈步,才能抓住稍纵即逝的机遇。从那天起,我卸下胆怯,勇敢改变。课堂上,我鼓起勇气举手发言,不再怕回答有误;学习遇到困难,我主动找老师请教,不再独自纠结;班级活动,我积极报名参与,不再因怕出错而旁观。我学着像那小花园中的绿植,主动向着光的方向靠拢。数月后的第二次入团报名,我不再犹豫,高高举起了手。我知道竞争依旧激烈,或许仍会失败,但纵然如此又何妨,勇敢迈出争取的一步,本就是一种成长。如今再逛小花园,那些叶片向阳的模样,早已刻进心底。它们教会我的,不仅是抓住机遇的道理,更是直面怯懦、勇敢向前的勇气。"

    result = essay_overlap_analysis(text1, text2)
    print("句子颗粒度重复率:", result["sentence_repeat_rate"])
    print("词组颗粒度的重复", result["word_repeat_rate"])
    print("对称相似度",result["symmetry_rate"])
    for d in result["details"][:3]:  # 仅展示前3个chunk结果
        print(d)

if __name__ == "__main__":
    main()