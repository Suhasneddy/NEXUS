import speech_recognition as sr

print("--- Available Audio Inputs ---")
for index, name in enumerate(sr.Microphone.list_microphone_names()):
    print(f"Index {index}: {name}")