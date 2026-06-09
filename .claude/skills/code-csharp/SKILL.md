---
name: code-csharp
description: "C# coding standards for .NET APIs and services."
when_to_use: "When writing or reviewing *.cs files."
user-invocable: false
model: sonnet
effort: medium
hub-skill-ids: [implementation, review, refactoring]
---

# Skill: C#

## Rules

REJECT if:
- `.Result` or `.Wait()` used on `Task` (blocks the thread; causes deadlocks in ASP.NET)
- Hardcoded connection strings or credentials in source
- Concrete types injected in constructors instead of interfaces
- `async` methods missing `CancellationToken` parameter

```csharp
// REJECT
public class UserService
{
    private readonly SqlConnection _conn = new("Server=prod;Password=secret");

    public User GetUser(int id) => _repo.GetAsync(id).Result;

    public async Task ProcessAsync() { /* no CancellationToken */ }
}
```

REQUIRE:
- PascalCase for all types, methods, properties, and public members
- `async`/`await` end-to-end; never mix blocking and async
- `CancellationToken ct = default` on all public async methods
- Interfaces for all injected dependencies

```csharp
// REQUIRE
public class UserService : IUserService
{
    private readonly IUserRepository _repo;

    public UserService(IUserRepository repo) => _repo = repo;

    public async Task<User> GetUserAsync(int id, CancellationToken ct = default)
        => await _repo.GetAsync(id, ct);
}
```

PREFER:
- `record` types over `class` for immutable data transfer objects
- Pattern matching over explicit type checks
- `using` declarations over `try`/`finally` for `IDisposable`

```csharp
// PREFER
public record UserDto(int Id, string Name);

public string Describe(object obj) => obj switch
{
    UserDto u => $"User {u.Name}",
    null => "null",
    _ => obj.ToString() ?? string.Empty
};
```

## Testing

REQUIRE:
- AAA structure (Arrange / Act / Assert) with inline comments on each section
- One assertion concept per test
- Descriptive names: `MethodName_Condition_ExpectedBehavior`

```csharp
[TestMethod]
public async Task GetUserAsync_ValidId_ReturnsUser()
{
    // Arrange
    var repo = Substitute.For<IUserRepository>();
    repo.GetAsync(1, default).Returns(new UserDto(1, "Alice"));
    var svc = new UserService(repo);

    // Act
    var result = await svc.GetUserAsync(1);

    // Assert
    Assert.AreEqual("Alice", result.Name);
}
```
