"""
Z80 Assembler Module
Provides assembly functionality for Z80 processor instructions.
"""

import re
from typing import List, Tuple, Dict, Optional


class Z80Assembler:
    """Simple Z80 assembler for converting assembly source to machine code."""
    
    # Registers
    REGISTERS = {'A', 'B', 'C', 'D', 'E', 'H', 'L', 'I', 'R'}
    REG_PAIRS = {'BC', 'DE', 'HL', 'SP', 'AF', 'IX', 'IY'}
    
    def __init__(self):
        self.labels = {}
        self.symbols = {}
        self.org_address = 0x0000
        self.current_address = 0x0000
        self.machine_code = []
        self.errors = []
        self.warnings = []
    
    def parse_source(self, source: str) -> List[str]:
        """Parse assembly source code into lines."""
        lines = []
        for line in source.split('\n'):
            # Remove comments (everything after ;)
            line = line.split(';')[0].strip()
            if line:
                lines.append(line)
        return lines
    
    def parse_line(self, line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Parse a single assembly line into label, mnemonic, and operands."""
        label = None
        mnemonic = None
        operands = None
        
        # Check for label (ends with :)
        if ':' in line:
            parts = line.split(':', 1)
            label = parts[0].strip()
            remaining = parts[1].strip()
        else:
            remaining = line
        
        # Split into mnemonic and operands
        if remaining:
            parts = remaining.split(None, 1)
            mnemonic = parts[0].strip().upper() if parts else None
            operands = parts[1].strip() if len(parts) > 1 else None
        
        return label, mnemonic, operands
    
    def evaluate_expression(self, expr: str) -> int:
        """Evaluate a numeric expression (hex, decimal, binary)."""
        if not expr:
            raise ValueError("Empty expression")
        
        expr = expr.strip().upper()
        
        # Handle labels
        if expr in self.labels:
            return self.labels[expr]
        
        # Handle $ as current address (standalone)
        if expr == '$':
            return self.current_address
        
        # Handle ORG as origin address
        if expr == 'ORG':
            return self.org_address
        
        # Handle hex (0x, $ prefix, or ending with H)
        if expr.startswith('0X'):
            return int(expr[2:], 16)
        elif expr.startswith('$'):
            return int(expr[1:], 16)
        elif expr.endswith('H'):
            return int(expr[:-1], 16)
        # Handle binary (ending with B)
        elif expr.endswith('B'):
            return int(expr[:-1], 2)
        # Handle decimal
        else:
            return int(expr)
    
    def assemble_instruction(self, mnemonic: str, operands: Optional[str]) -> bytes:
        """Assemble a single instruction into machine code."""
        try:
            mnemonic = mnemonic.upper()
            
            # Handle single-byte instructions
            single_byte_ops = {
                'NOP': 0x00,
                'HALT': 0x76,
                'DI': 0xF3,
                'EI': 0xFB,
                'RLCA': 0x07,
                'RRCA': 0x0F,
                'RLA': 0x17,
                'RRA': 0x1F,
                'DAA': 0x27,
                'CPL': 0x2F,
                'SCF': 0x37,
                'CCF': 0x3F,
                'RET': 0xC9,
            }
            
            if mnemonic in single_byte_ops:
                return bytes([single_byte_ops[mnemonic]])
            
            # Handle LD r, r' (register to register) - check this FIRST before immediate load
            if mnemonic == 'LD' and operands:
                parts = [p.strip() for p in operands.split(',')]
                if len(parts) == 2 and parts[0] in self.REGISTERS and parts[1] in self.REGISTERS:
                    src = parts[0]
                    dst = parts[1]
                    reg_codes = {'B': 0, 'C': 1, 'D': 2, 'E': 3, 'H': 4, 'L': 5, 'A': 7}
                    opcode = 0x40 + (reg_codes[src] << 3) + reg_codes[dst]
                    return bytes([opcode])
            
            # Handle LD r, n (8-bit immediate load)
            if mnemonic == 'LD' and operands:
                parts = [p.strip() for p in operands.split(',')]
                if len(parts) == 2 and parts[0] in self.REGISTERS:
                    reg = parts[0]
                    # Only try to evaluate if it's not a register
                    if parts[1] not in self.REGISTERS:
                        try:
                            value = self.evaluate_expression(parts[1])
                            reg_codes = {'B': 0x06, 'C': 0x0E, 'D': 0x16, 'E': 0x1E, 
                                        'H': 0x26, 'L': 0x2E, 'A': 0x3E}
                            if reg in reg_codes:
                                return bytes([reg_codes[reg], value & 0xFF])
                        except:
                            self.errors.append(f"Invalid immediate value for LD {reg}: {parts[1]}")
                            return b''
            
            # Handle LD (HL), n
            if mnemonic == 'LD' and operands and '(HL)' in operands:
                parts = [p.strip() for p in operands.split(',')]
                if len(parts) == 2 and parts[0] == '(HL)':
                    value = self.evaluate_expression(parts[1])
                    return bytes([0x36, value & 0xFF])
            
            # Handle LD (IX+d), n and LD (IY+d), n
            if mnemonic == 'LD' and operands:
                if '(IX+' in operands or '(IY+' in operands:
                    match = re.match(r'\((IX|IY)\+([^\)]+)\),\s*(.+)', operands)
                    if match:
                        idx_reg = match.group(1)
                        offset = self.evaluate_expression(match.group(2))
                        value = self.evaluate_expression(match.group(3))
                        prefix = 0xDD if idx_reg == 'IX' else 0xFD
                        offset_byte = offset & 0xFF
                        if offset_byte > 127:
                            offset_byte = offset_byte - 256  # Two's complement
                        return bytes([prefix, 0x36, offset_byte & 0xFF, value & 0xFF])
            
            # Handle INC r
            if mnemonic == 'INC' and operands and operands in self.REGISTERS:
                reg_codes = {'B': 0x04, 'C': 0x0C, 'D': 0x14, 'E': 0x1C, 
                            'H': 0x24, 'L': 0x2C, 'A': 0x3C}
                if operands in reg_codes:
                    return bytes([reg_codes[operands]])
            
            # Handle DEC r
            if mnemonic == 'DEC' and operands and operands in self.REGISTERS:
                reg_codes = {'B': 0x05, 'C': 0x0D, 'D': 0x15, 'E': 0x1D, 
                            'H': 0x25, 'L': 0x2D, 'A': 0x3D}
                if operands in reg_codes:
                    return bytes([reg_codes[operands]])
            
            # Handle JP nn
            if mnemonic == 'JP' and operands:
                addr = self.evaluate_expression(operands)
                return bytes([0xC3, addr & 0xFF, (addr >> 8) & 0xFF])
            
            # Handle JP cc, nn
            if mnemonic == 'JP' and operands:
                parts = [p.strip() for p in operands.split(',')]
                if len(parts) == 2:
                    conditions = {'NZ': 0xC2, 'Z': 0xCA, 'NC': 0xD2, 'C': 0xDA,
                                'PO': 0xE2, 'PE': 0xEA, 'P': 0xF2, 'M': 0xFA}
                    if parts[0] in conditions:
                        addr = self.evaluate_expression(parts[1])
                        return bytes([conditions[parts[0]], addr & 0xFF, (addr >> 8) & 0xFF])
            
            # Handle JR e
            if mnemonic == 'JR' and operands:
                # Calculate relative offset (this is a simplified version)
                # In a real assembler, this would need to be calculated after first pass
                offset = self.evaluate_expression(operands)
                return bytes([0x18, offset & 0xFF])
            
            # Handle JR cc, e
            if mnemonic == 'JR' and operands:
                parts = [p.strip() for p in operands.split(',')]
                if len(parts) == 2:
                    conditions = {'NZ': 0x20, 'Z': 0x28, 'NC': 0x30, 'C': 0x38}
                    if parts[0] in conditions:
                        offset = self.evaluate_expression(parts[1])
                        return bytes([conditions[parts[0]], offset & 0xFF])
            
            # Handle CALL nn
            if mnemonic == 'CALL' and operands:
                addr = self.evaluate_expression(operands)
                return bytes([0xCD, addr & 0xFF, (addr >> 8) & 0xFF])
            
            # Handle CALL cc, nn
            if mnemonic == 'CALL' and operands:
                parts = [p.strip() for p in operands.split(',')]
                if len(parts) == 2:
                    conditions = {'NZ': 0xC4, 'Z': 0xCC, 'NC': 0xD4, 'C': 0xDC,
                                'PO': 0xE4, 'PE': 0xEC, 'P': 0xF4, 'M': 0xFC}
                    if parts[0] in conditions:
                        addr = self.evaluate_expression(parts[1])
                        return bytes([conditions[parts[0]], addr & 0xFF, (addr >> 8) & 0xFF])
            
            # Handle RET cc
            if mnemonic == 'RET' and operands:
                conditions = {'NZ': 0xC0, 'Z': 0xC8, 'NC': 0xD0, 'C': 0xD8,
                            'PO': 0xE0, 'PE': 0xE8, 'P': 0xF0, 'M': 0xF8}
                if operands in conditions:
                    return bytes([conditions[operands]])
            
            # Handle ADD A, n
            if mnemonic == 'ADD' and operands and operands.startswith('A,'):
                operand = operands[2:].strip()
                # Check if it's a register
                if operand in self.REGISTERS:
                    reg_codes = {'B': 0x80, 'C': 0x81, 'D': 0x82, 'E': 0x83, 
                                'H': 0x84, 'L': 0x85, 'A': 0x87}
                    if operand in reg_codes:
                        return bytes([reg_codes[operand]])
                else:
                    # It's an immediate value
                    try:
                        value = self.evaluate_expression(operand)
                        return bytes([0xC6, value & 0xFF])
                    except:
                        self.errors.append(f"Invalid ADD operand: {operand}")
                        return b''
            
            # Handle SUB n
            if mnemonic == 'SUB' and operands:
                value = self.evaluate_expression(operands)
                return bytes([0xD6, value & 0xFF])
            
            # Handle AND n
            if mnemonic == 'AND' and operands:
                value = self.evaluate_expression(operands)
                return bytes([0xE6, value & 0xFF])
            
            # Handle OR n
            if mnemonic == 'OR' and operands:
                value = self.evaluate_expression(operands)
                return bytes([0xF6, value & 0xFF])
            
            # Handle XOR n
            if mnemonic == 'XOR' and operands:
                value = self.evaluate_expression(operands)
                return bytes([0xEE, value & 0xFF])
            
            # Handle CP n
            if mnemonic == 'CP' and operands:
                value = self.evaluate_expression(operands)
                return bytes([0xFE, value & 0xFF])
            
            # Handle XOR A
            if mnemonic == 'XOR' and operands == 'A':
                return bytes([0xAF])
            
            # Handle LD BC, nn / LD DE, nn / LD HL, nn / LD SP, nn
            if mnemonic == 'LD' and operands:
                parts = [p.strip() for p in operands.split(',')]
                if len(parts) == 2 and parts[0] in self.REG_PAIRS:
                    pair_codes = {'BC': 0x01, 'DE': 0x11, 'HL': 0x21, 'SP': 0x31}
                    if parts[0] in pair_codes:
                        addr = self.evaluate_expression(parts[1])
                        return bytes([pair_codes[parts[0]], addr & 0xFF, (addr >> 8) & 0xFF])
            
            # Handle LD IX, nn / LD IY, nn
            if mnemonic == 'LD' and operands:
                parts = [p.strip() for p in operands.split(',')]
                if len(parts) == 2 and parts[0] in ['IX', 'IY']:
                    prefix = 0xDD if parts[0] == 'IX' else 0xFD
                    addr = self.evaluate_expression(parts[1])
                    return bytes([prefix, 0x21, addr & 0xFF, (addr >> 8) & 0xFF])
            
            # Handle ORG directive
            if mnemonic == 'ORG':
                if not operands:
                    self.errors.append("ORG directive requires an address parameter")
                    return b''
                try:
                    self.org_address = self.evaluate_expression(operands)
                    self.current_address = self.org_address
                    return b''
                except Exception as e:
                    self.errors.append(f"Error evaluating ORG address: {str(e)}")
                    return b''
            
            # Handle DB directive (define byte)
            if mnemonic == 'DB' or mnemonic == 'DEFB':
                if not operands:
                    self.errors.append("DB directive requires at least one value")
                    return b''
                values = []
                for part in operands.split(','):
                    part = part.strip()
                    if part:
                        try:
                            values.append(self.evaluate_expression(part) & 0xFF)
                        except:
                            # Handle strings
                            if part.startswith('"') and part.endswith('"'):
                                values.extend(ord(c) for c in part[1:-1])
                            elif part.startswith("'") and part.endswith("'"):
                                values.extend(ord(c) for c in part[1:-1])
                            else:
                                self.errors.append(f"Invalid DB value: {part}")
                return bytes(values)
            
            # Handle DW directive (define word)
            if mnemonic == 'DW' or mnemonic == 'DEFW':
                if not operands:
                    self.errors.append("DW directive requires at least one value")
                    return b''
                values = []
                for part in operands.split(','):
                    part = part.strip()
                    if part:
                        try:
                            value = self.evaluate_expression(part)
                            values.append(value & 0xFF)
                            values.append((value >> 8) & 0xFF)
                        except Exception as e:
                            self.errors.append(f"Invalid DW value: {part} - {str(e)}")
                return bytes(values)
            
            # Handle DS directive (define storage)
            if mnemonic == 'DS' or mnemonic == 'DEFS':
                if not operands:
                    self.errors.append("DS directive requires a count parameter")
                    return b''
                try:
                    count = self.evaluate_expression(operands)
                    if count < 0:
                        self.errors.append(f"DS count cannot be negative: {count}")
                        return b''
                    return b'\x00' * count
                except Exception as e:
                    self.errors.append(f"Error evaluating DS count: {str(e)}")
                    return b''
            
            # Handle EQU directive (equate)
            if mnemonic == 'EQU':
                # This should be handled in label processing
                return b''
            
            # Handle END directive
            if mnemonic == 'END':
                return b''
            
            # Unknown instruction
            self.errors.append(f"Unknown instruction or directive: {mnemonic}")
            return b''
        except Exception as e:
            self.errors.append(f"Error assembling instruction '{mnemonic}': {str(e)}")
            return b''
    
    def assemble(self, source: str, org_address: int = 0x0000) -> Tuple[bytes, List[str], List[str]]:
        """
        Assemble source code into machine code.
        
        Args:
            source: Assembly source code
            org_address: Origin address (default 0x0000)
        
        Returns:
            Tuple of (machine_code, errors, warnings)
        """
        try:
            self.org_address = org_address
            self.current_address = org_address
            self.machine_code = []
            self.errors = []
            self.warnings = []
            self.labels = {}
            
            lines = self.parse_source(source)
            
            # Single pass: collect labels and generate code
            for line in lines:
                label, mnemonic, operands = self.parse_line(line)
                
                # Store label address before processing instruction
                if label and mnemonic != 'EQU':
                    self.labels[label] = self.current_address
                
                # Handle END directive
                if mnemonic == 'END':
                    break
                
                # Handle EQU directive
                if mnemonic == 'EQU' and label:
                    try:
                        self.labels[label] = self.evaluate_expression(operands)
                    except Exception as e:
                        self.errors.append(f"Error evaluating EQU for {label}: {str(e)}")
                    continue
                
                # Assemble instruction
                if mnemonic:
                    code = self.assemble_instruction(mnemonic, operands)
                    self.machine_code.extend(code)
                    self.current_address += len(code)
            
            return bytes(self.machine_code), self.errors, self.warnings
        except Exception as e:
            self.errors.append(f"Fatal assembly error: {str(e)}")
            return b'', self.errors, self.warnings


def assemble_z80_source(source: str, org_address: int = 0x0000) -> Tuple[bytes, List[str], List[str]]:
    """
    Convenience function to assemble Z80 source code.
    
    Args:
        source: Assembly source code
        org_address: Origin address (default 0x0000)
    
    Returns:
        Tuple of (machine_code, errors, warnings)
    """
    assembler = Z80Assembler()
    return assembler.assemble(source, org_address)
