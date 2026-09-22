# CAC-3-sinclair-zx81-lambda-8300-clone
---

## CAC-3 is a Sinclair ZX81/Lambda 8300 clone.
* This repository contains the documents, manual and analysis tools for the CAC-3 computer.
---

### CAC-3 Specifications:
* manufacturer: 东深科教公司  
* cpu:    Z80A  
* memory: 16 kB  
* rom:    8 kB (Basic) + 8 kB (monitor/assembly)
---

## The description of the files and folders in this repostitory:

* 📁 **documents/**
  * 📄 `cac-3_manual_scan.pdf` — Scanned CAC-3 document in PDF format.
  * 📄 `lambda8300_perfect.csv` — Lambda 8300 Character Set.

* 📁 **img/**
  * 📄 `81simulator-01.png` — Simulator setup for CAC-3.
  * 📄 `81simulator-02.png` — Simulator setup for CAC-3.
  * 📄 `81simulator-03.png` — Simulator setup for CAC-3.
  * 📄 `81simulator-04.png` — Simulator setup for CAC-3.
  * 📄 `81simulator-05.png` — Simulator setup for CAC-3.
  * 📄 `81simulator-06.png` — Simulator setup for CAC-3.
  * 📄 `character_set.png` — Lambda 8300 Character set mapping table.

* 📁 **rom/** — CAC-3 16k rom, first 8k for Basic interpretor, second 8k Z80 ASM and Monitor.
* 📁 **src/** — Source code directory to CAC-3 tools.
  * 📄 `main.py` — Main page (using Tk library).
  * 📄 `main_pyqt.py` — Main page (using Qt library).
    
* 📄 `README.md` — Project documentation and description file.
* 📄 `requirements.txt` — Python or software package dependencies list.
    
---

### CAC-3 Tape Interface Specification

The tape interface uses 3.5mm "EAR" and "MIC" jacks to save and load data.
It encodes data bits as a series of pulses with a standard data rate (baud rate)
between 250 and 400 bits per second (bps).

Bit EncodingThe tape stores digital bits as audio tones. Each pulse uses
a high signal of 150 μs and a low signal of 150 μs.  
* '0' bit: Consists of 4 consecutive pulses, followed by a silence of 1300 μs.
* '1' bit: Consists of 9 consecutive pulses, followed by a silence of 1300 μs.  

Voltage Levels
* EAR input (Loading): The computer requires a minimum audio signal
of about 2 V peak-to-peak from your playback device to read the data correctly.
* Threshold voltage: The internal chip requires at least 0.7 V to trigger a pulse
reading.

 脉冲宽度/冲群调制（Pulse-Burst Modulation）规范。
 1. 物理层音频信号参数磁带接口通常通过 3.5mm AUX 音频线连接普通的盒式磁带录音机（EAR / MIC 接口）。
 信号物理特征如下：  
 * 载波与波形： 使用方波或近似正弦波的音频高频冲群（Burst）。
 * 基本脉冲周期（Pulse Period）：一个完整的“正负脉冲”（1 次 High + 1 次 Low）：300 µs（约 3.33 kHz）。
 高电平持续时间：约 150 µs；低电平持续时间：约 150 µs。

 2. 数据位（Bit）编码标准，非使用常见的 Kansas City 标准（连续的两个高低频率），
而是采用“脉冲串 + 静音间隔”的方式来区分逻辑 0 和 1：  

| 逻辑状态 | 脉冲串数量（Burst Count）| 脉冲总时长 | 后续静音时长（Silence） | 单比特总耗时 |
| --- | --- |
| Bit0 | 4个连续3.33kHz脉冲 | 4x300us | 1300µs (1.3ms) | 2.5 ms (400 bps) |
| Bit1 | 8~9个连续3.33kHz脉冲 | 9x300us | 1300µs (1.3ms) | 4.0 ms (250 bps) |

3. 磁带文件结构（Tape File Framing）  
当使用 BASIC 命令 SAVE "NAME" 保存程序到磁带时，输出的音频信号结构如下：
   1. 导轨信号：
      录音开始前有长达数秒的3.33 kHz（周期 300 µs）高频方波脉冲。
   2. 文件名（Header / Name）：
      保存输入的程序名称字符（以 ASCII / 字符映射码形式存储）。
   3. 主数据块（Data Payload）：
      包含 RAM 系统变量区（System Variables）和 BASIC 源码存储区（RAM 地址 $4000 之后的数据）。
      采用无校验或简单的流式字节排列。
   4. 尾部（End Gap）：数据结束后恢复为静音段。 
   5. 在静音段，实际还有50/60Hz的视频同步信号，为单个脉冲。

---

### CAC-3 Tape file formats

1. Tape saved in Monitoring Mode with command "W xxxx:yyyy":  
前面5个字节文件头，内容为ED 54 6F D6 50，对应的CAC-3字符为mToVP （Memory To Voice taPe)，
紧跟着是两个字节起始地址 (xxxx)，再跟两个字节数据长度 (yyyy-xxxx)，
从第十个字节开始是正式内容。结尾还多一个字节，内容不固定。大约是校验用的。

2. CAC-3的BASIC文件格式，以SAVE命令存储的磁带文件。
   1. 二进制文件开始的几个字节是文件名，即SAVE "FILENAME"命令里的文件名“FILENAME”，每个字节的第七位是
   lambda8300的字符，文件名最后一个字符的最高位为1，可通过这种方式找到文件名的结尾。
   2. 文件名后跟一个FF，是116个字节的系统变量区的开始，有的单字节，有的双字节，高字节在后，显示hex双字节内容，
   3. 之后视频缓冲区，32x24，每行32字符加0x76结尾，开始也有0x76字节。共33x24+1=793个字节。
   4. 之后为basic程序。
   5. 116个字节的系统变量，下面是已知的定义：
     offset  size    content
     00H     1       FFH
     01H     2       407DH
     03H     2       4396H
     05H     2       407EH
     07H     2       4396H + (basic code length, end with FFH 80H) + 1
     33H     32      0, printer buffer
     53H     1       76H
     54H     32      0
     74H     1       76H, 视频缓冲开始

