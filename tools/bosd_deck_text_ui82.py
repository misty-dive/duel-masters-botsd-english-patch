#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib

# Retail DECK/*.DAT text fields: 0x06..0x2D = 40-byte callout, 0x2E..0x41 = 20-byte deck title.
# All card/deck composition bytes beginning at 0x42 are preserved verbatim.
T = {
'00_1.DAT':("こいつで道を切り開く！","ボル勝舞","This will clear the way!","Bolshack Shobu"),
'00_2.DAT':("この一枚に全てをかける！！","ボルバル勝舞","I'm betting everything on this card!!","Bombazar Shobu"),
'01_1.DAT':("ぼくは負けられないんだ！","聖天使の一撃","I can't lose this duel!","Holy Angel Strike"),
'01_2.DAT':("遠慮なく全力でいくよ。","守護者の怒り","I won't hold anything back.","Guardian's Fury"),
'02_1.DAT':("残念だったな、こいつで終わりだ！","ギガ・デス","Too bad. This is the end!","Giga Death"),
'02_2.DAT':("地獄を見せてやる！！","デス・ドラグーン","I'll show you hell!!","Death Dragoon"),
'03_1.DAT':("切札、だしちゃいまーす♪","ラブ☆クリスタル","Time for my trump card!","Love Crystal"),
'03_2.DAT':("Ｃ・パラディンちゃん、召喚！！","ラブ・アサシン","Crystal Paladin, come on out!!","Love Assassin"),
'04_1.DAT':("これでどうだ！！","天空の大勇者","How about this!!","Sky Hero"),
'04_2.DAT':("誰にも、じゃまはさせないぞ！","大自然の聖天使","No one will stand in my way!","Nature Holy Angel"),
'06_1.DAT':("全ては最強の名のもとに！！","超竜火炎斬","All in the name of the strongest!!","Super Dragon Slash"),
'06_2.DAT':("超竜軍団　集結せよ！","天下無敵超竜不敗","Super Dragons, assemble!","Invincible Dragons"),
'06_3.DAT':("それ！　それ！　それ！　それ！！","フルスピード","Go! Go! Go! Go!!","Full Speed"),
'06_4.DAT':("勝利に向かって飛び立つのだ！","ハイ・ペガサス","Fly onward to victory!","High Pegasus"),
'06_5.DAT':("私の勝利は確実だな。","聖天使強襲","My victory is assured.","Holy Angel Raid"),
'06_6.DAT':("わかるか？　この一手の意味が！","フレームパンチ","Do you see what this move means?","Flame Punch"),
'07_1.DAT':("戒めを解き放ち　我が剣となれ！","ホーリーカッター","Break your bonds and become my blade!","Holy Cutter"),
'07_2.DAT':("我らに聖なる力を与えたまえ！","ペトディエーター","Grant us your holy power!","Petodiator"),
'08_1.DAT':("何しようともう手遅れだよーん。","ＧＹＵ★リターン","Whatever you do, it's too late!","GYU Return"),
'08_2.DAT':("ぼくちゃんチョー天才！！","嫌★がらせ","I'm a total genius!!","Harassment"),
'09_1.DAT':("そろそろ反撃させてもらうぜ！","サイバー・ゴッド","Now it's my turn to fight back!","Cyber God"),
'09_2.DAT':("ふっとばせ！","ハイドロ・ゴッド","Blow 'em away!","Hydro God"),
'10_1.DAT':("残念だったわね、これでおわりよ。","タップストリーム","Too bad. This is the end.","Tap Stream"),
'10_2.DAT':("みんな、クズなのよ！","ドラゴンストーム","You're all trash!","Dragon Storm"),
'11_1.DAT':("ぼくの美しさはカードも虜にする。","暗殺者復活","Even the cards adore my beauty.","Assassin Revival"),
'11_2.DAT':("美しく散るがよい！","聖霊王降臨","Perish beautifully!","Holy King Descends"),
'12_1.DAT':("これが愛の力です！","鉄壁の愛","This is the power of love!","Ironclad Love"),
'12_2.DAT':("ぼくの愛が届いたようです。","反撃の愛","It seems my love reached you.","Love Counter"),
'13_1.DAT':("見よ！　これが真の速攻ぞ！！","猛火強襲の計","Behold! This is true speed!!","Blazing Rush"),
'13_2.DAT':("速攻に勝る戦術なし！！","烈火奇襲の計","No strategy beats a rush!!","Fire Raid"),
'14_1.DAT':("マナ全開で攻撃や～！","マナや～♪","Full mana, full attack!","Mana!"),
'14_2.DAT':("どうやらわいの勝ちでんな。","マナやマナや～♪","Looks like I win this one.","More Mana!"),
'15_1.DAT':("おいら絶対負けないべ！","ムシ軍団出撃だべ","I ain't gonna lose!","Bug Army Sortie"),
'15_2.DAT':("これでおいらの勝ちだべ！","ムシ軍団突撃だべ","This makes me the winner!","Bug Army Charge"),
'16_1.DAT':("どっきり丸秘作戦発動にょろ！","まなごろし！","Secret surprise plan, go!","Mana Killer"),
'16_2.DAT':("こいつをくらいやがれ！","魔那故露死！","Take this!","Mana Killer"),
'17_1.DAT':("しょんべん、チビんなよ！！","デッキブレイカー","Don't wet yourself!!","Deck Breaker"),
'17_2.DAT':("ガキだろうが容赦しねーぜ！","無限飛竜","Kid or not, I won't go easy!","Infinite Dragon"),
'18_2.DAT':("汝の身を炎で焼く尽くす！","ボルバ・ソウル","The flames shall consume you!","Bolba Soul"),
'19_2.DAT':("我を倒すことなど不可能！","ホーリー・スター","It is impossible to defeat me!","Holy Star"),
'20_2.DAT':("闇に囚われてしまえ！","ロスト・ヘル","Be swallowed by darkness!","Lost Hell"),
'21_2.DAT':("水の化身が汝を打ち破る！","ギガ・スレイヤー","The avatar of water shall crush you!","Giga Slayer"),
'22_2.DAT':("自然の怖さを教えてやろう。","ホーン・コマンド","I will teach you nature's terror.","Horn Command"),
'23_2.DAT':("滅びてしまえ！","破滅の暗黒超竜","Be destroyed!","Dark Dragon Doom"),
'24_1.DAT':("ぼくを甘く見ないでください！","サバイバー強襲","Please don't underestimate me!","Survivor Assault"),
'24_2.DAT':("すべて作戦通りです！","ベジタルウェーブ","Everything is going as planned!","Vegital Wave"),
'25_1.DAT':("残念だが、神は私の味方らしい。","スペルリサイクル","Sorry, but the gods favor me.","Spell Recycle"),
'25_2.DAT':("私の前にひざまずくがよい！","タップ・パンチ","Kneel before me!","Tap Punch"),
'25_3.DAT':("こんなんで、どうかの？","リキッド・ブルー","How about this?","Liquid Blue"),
'25_4.DAT':("全てはここから始まる！！","究極進化七変化","It all begins here!!","Ultimate Evolution"),
'25_5.DAT':("これがクールな戦術だ！","緑神龍カムヒア","Now this is a cool tactic!","Green Dragon Here"),
'26_2.DAT':("キタキター！　切り札キター！！","男前スペシャル","Here it is! My trump card!!","Handsome Special"),
'27_1.DAT':("逃げるんなら今のうちじゃぞ！","悪魔神降臨","Now's your chance to run!","Demon God Descends"),
'27_2.DAT':("んじゃわしはこのカードを使うよ。","獄門死","Then I'll use this card.","Gate of Death"),
'27_3.DAT':("たまには力押しも、いいもんじゃの","パワー・アタック","Sometimes brute force is best.","Power Attack"),
'27_4.DAT':("この攻撃を防げるかな？","ウェーブ・Ｖ","Can you stop this attack?","Wave V"),
'27_5.DAT':("捨ててもらおうかの。","生と死の輪舞","I'll have you discard that.","Life-Death Rondo"),
'27_6.DAT':("真の恐怖はこれからじゃぞ！","シャドウハンター","The real terror starts now!","Shadow Hunter"),
'28_1.DAT':("これでキメるぜ！","進化猛攻","This will finish it!","Evolution Rush"),
'28_2.DAT':("このカードを使うぜ！","烈火特攻","I'll use this card!","Blazing Assault"),
}

def sha(b): return hashlib.sha256(b).hexdigest()
def read_field(b,off,n): return b[off:off+n].split(b'\0',1)[0].decode('cp932')
def enc_field(s,n):
    x=s.encode('ascii')
    if len(x)>=n: raise ValueError(f'field too long ({len(x)} >= {n}): {s!r}')
    return x+b'\0'*(n-len(x))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--report',type=Path);a=ap.parse_args()
    files=sorted(a.input_dir.glob('*.DAT'))
    if set(p.name for p in files)!=set(T):
        missing=sorted(set(T)-set(p.name for p in files)); extra=sorted(set(p.name for p in files)-set(T))
        raise SystemExit(f'DECK inventory mismatch missing={missing} extra={extra}')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    lines=['UI82 DECK DATA TEXT LOCALIZATION','slots: callout 0x06+40, title 0x2E+20; bytes >=0x42 preserved']
    manifest=[]
    for p in files:
        jp1,jp2,en1,en2=T[p.name]; b=p.read_bytes()
        if len(b)<0x42: raise SystemExit(f'{p.name}: too short')
        got1=read_field(b,0x06,40); got2=read_field(b,0x2E,20)
        if (got1,got2)!=(jp1,jp2): raise SystemExit(f'{p.name}: source gate failed: {(got1,got2)!r}')
        nb=bytearray(b); nb[0x06:0x2E]=enc_field(en1,40); nb[0x2E:0x42]=enc_field(en2,20)
        out=a.output_dir/p.name; out.write_bytes(nb)
        if len(nb)!=len(b) or nb[:0x06]!=b[:0x06] or nb[0x42:]!=b[0x42:]: raise RuntimeError(f'{p.name}: containment failed')
        if read_field(nb,0x06,40)!=en1 or read_field(nb,0x2E,20)!=en2: raise RuntimeError(f'{p.name}: output decode failed')
        manifest.append(f'{p.name}\t{sha(b)}\t{sha(nb)}\t{en1}\t{en2}')
    lines += [f'files={len(files)}','all_sizes=UNCHANGED','all_header_bytes_0x00_0x05=UNCHANGED','all_card_composition_bytes_0x42_end=BYTE-IDENTICAL','source_cp932_fields=VERIFIED','english_fields=ASCII_AND_NUL_PADDED','RESULT=PASS','', 'file\tinput_sha256\toutput_sha256\tcallout\tdeck_title']+manifest
    text='\n'.join(lines)+'\n'; print(text,end='')
    if a.report: a.report.write_text(text,encoding='utf-8')
if __name__=='__main__':main()
