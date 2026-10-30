import spub

note = "This is a permanent SPUB research checkpoint."

package, key = spub.encrypt(note)

print("Original bytes:", len(note.encode("utf-8")))
print("Package bytes:", len(package))

recovered = spub.decrypt(package, key)

print("Recovered:", recovered)