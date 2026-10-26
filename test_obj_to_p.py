"""Test script for OBJ to P file conversion"""

from z80_assembler import assemble_z80_source, convert_obj_to_p, assemble_to_p_file

# Test 1: Simple assembly code
test_source = """
    ORG 0x4000
    LD A, 10
    LD B, 20
    ADD A, B
    RET
"""

print("Test 1: Assembling simple Z80 code...")
machine_code, errors, warnings = assemble_z80_source(test_source, org_address=0x4000)

if errors:
    print(f"Assembly errors: {errors}")
else:
    print(f"Machine code: {machine_code.hex()}")
    print(f"Length: {len(machine_code)} bytes")

# Test 2: Convert to P file format
print("\nTest 2: Converting machine code to P file format...")
p_file = convert_obj_to_p(machine_code, start_address=0x4000)
print(f"P file header: {p_file[:9].hex()}")
print(f"Expected header: ED546FD650")
print(f"Start address: {int.from_bytes(p_file[5:7], byteorder='big'):04X}")
print(f"Data length: {int.from_bytes(p_file[7:9], byteorder='big')}")
print(f"Full P file: {p_file.hex()}")

# Test 3: Direct assembly to P file
print("\nTest 3: Direct assembly to P file...")
p_file_direct, errors, warnings = assemble_to_p_file(test_source, org_address=0x4000)

if errors:
    print(f"Assembly errors: {errors}")
else:
    print(f"P file (direct): {p_file_direct.hex()}")
    print(f"Matches conversion: {p_file == p_file_direct}")

# Test 4: Verify header format
print("\nTest 4: Verifying header format...")
expected_header = bytes.fromhex("ED546FD650")
actual_header = p_file[:5]
print(f"Expected header: {expected_header.hex()}")
print(f"Actual header: {actual_header.hex()}")
print(f"Header correct: {expected_header == actual_header}")

print("\nAll tests completed!")
